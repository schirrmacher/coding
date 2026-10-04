"""Private directory grants feed the same file and network policy."""
import json
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_support import ROOT, load_module, run_bash, write_config

loader = load_module("local_config", ROOT / "lib/load_config.py")


class LocalConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.public = self.root / "public.toml"
        self.private = self.root / "local.toml"
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        self.other = self.root / "other"
        self.other.mkdir()
        self.skills = self.project / "skills"
        self.skills.mkdir()
        write_config(self.public, {"apps": [
            {"name": "writer", "endpoints": ["BASE.example."]},
            {"name": "reader", "endpoints": ["reader.example"]},
            {"name": "unlisted", "endpoints": ["unlisted.example"]},
        ]})

    def load(self, entries):
        write_config(self.private, {"directories": entries})
        return loader.read_config(self.public, self.private)

    def shell(self, command):
        return run_bash(f'''source {shlex.quote(str(ROOT / 'bin/sandbox'))}
source {shlex.quote(str(ROOT / 'lib/render_apparmor.sh'))}
CONFIG={shlex.quote(str(self.public))}
LOCAL_CONFIG={shlex.quote(str(self.private))}
APP=writer; DIRECTORY_ARGS=()
{command}
''')

    def test_all_grants_and_endpoints_are_combined_per_app(self):
        data = self.load([
            {"path": str(self.project), "apps": ["writer"], "read": ["reader"],
             "endpoints": ["PROJECT.example", "base.example"]},
            {"path": str(self.other), "apps": ["writer"], "endpoints": ["other.example"]},
            {"path": str(self.skills), "read": ["writer"]},
        ])
        writer, reader, unlisted = data["apps"]
        self.assertEqual(writer["dir"]["write"], [str(self.project), str(self.other)])
        self.assertEqual(writer["dir"]["read"], [str(self.skills)])
        self.assertEqual(writer["endpoints"], ["base.example", "project.example", "other.example"])
        self.assertEqual(reader["dir"]["read"], [str(self.project)])
        self.assertEqual(reader["endpoints"], ["reader.example", "project.example", "base.example"])
        self.assertNotIn("dir", unlisted)
        self.assertEqual(unlisted["endpoints"], ["unlisted.example"])

    def test_absent_private_file_has_no_project_fallback(self):
        data = loader.read_config(self.public, self.private)
        self.assertEqual(data["config_paths"], [str(self.public)])
        result = self.shell("resolve_directories")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_default_private_location_uses_account_home(self):
        private = self.root / ".config/sandbox/local.toml"
        private.parent.mkdir(parents=True)
        write_config(private, {"directories": [{"path": "${HOME}/other", "apps": ["writer"]}]})
        with patch.object(loader, "user_home", return_value=str(self.root)):
            data = loader.read_config(self.public)
        self.assertEqual(data["apps"][0]["dir"]["write"], [str(self.other)])
        self.assertEqual(data["config_paths"], [str(self.public), str(private)])

    def test_invalid_private_entries_stop_loading(self):
        cases = [
            ({"path": "relative", "apps": ["writer"]}, "absolute"),
            ({"path": str(self.project), "apps": ["unknown"]}, "unknown"),
            ({"path": str(self.project), "apps": "writer"}, "array"),
            ({"path": str(self.project), "apps": [1]}, "strings"),
            ({"path": str(self.project), "apps": ["writer"], "read": ["writer"]}, "both"),
            ({"path": str(self.project), "apps": ["writer"], "endpoints": "example.com"}, "array"),
            ({"path": str(self.project)}, "at least one"),
            ({"path": str(self.project), "apps": ["writer"], "unknown": True}, "only"),
        ]
        for entry, message in cases:
            with self.subTest(entry=entry), self.assertRaisesRegex(ValueError, message):
                self.load([entry])
        with self.assertRaisesRegex(ValueError, "local.toml"):
            self.load([{"path": str(self.root / "missing"), "apps": ["writer"]}])
        self.private.write_text('directories = [')
        with self.assertRaisesRegex(ValueError, "local.toml"):
            loader.read_config(self.public, self.private)

    def test_symlink_aliases_cannot_duplicate_directory_entries(self):
        link = self.root / "link"
        link.symlink_to(self.project)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.load([{"path": str(path), "apps": ["writer"]} for path in (self.project, link)])

    def test_both_configs_are_protected_and_nested_readonly_grants_win(self):
        self.load([
            {"path": str(self.project), "apps": ["writer"]},
            {"path": str(self.skills), "read": ["writer"]},
        ])
        result = self.shell('SUDO_UID=$(id -u); app_file_rules writer "$PWD"; prepare_directories; prepare_mounts_and_environment; printf "%s\\n" "${CONFIG_ARGS[@]}"')
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in (self.public, self.private):
            self.assertIn(f'deny "{path}" wkl,', result.stdout)
            self.assertIn(f'--ro-bind\n{path}\n{path}', result.stdout)
        self.assertIn(f'deny "{self.skills}/**" wl,', result.stdout)

    def test_directory_flag_changes_cwd_without_narrowing_grants(self):
        self.load([{"path": str(path), "apps": ["writer"]} for path in (self.project, self.other)])
        result = self.shell(f'DIRECTORY_ARGS=({shlex.quote(str(self.skills))}); SUDO_UID=$(id -u); prepare_directories; printf "%s\\n" "$WORKING_DIRECTORY" "${{DIRECTORIES[@]}}"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.skills), str(self.project), str(self.other)])
        for arguments, message in ((str(self.root), "not allowed"),
                                   (f'{shlex.quote(str(self.project))} {shlex.quote(str(self.other))}', "only once")):
            result = self.shell(f'DIRECTORY_ARGS=({arguments}); prepare_directories')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(message, result.stderr)

    def test_stale_policy_rejects_launch_until_runtime_is_regenerated(self):
        data = self.load([{"path": str(self.project), "apps": ["writer"]}])
        runtime = self.root / "runtime.json"
        runtime.write_text(json.dumps({"policy_fingerprint": data["policy_fingerprint"],
                                      "apps": [{"name": "writer", "ip": "10.77.0.1"}],
                                      "proxy": {"sni_port": 3128}}))
        command = f'''PROXY_CONFIG={shlex.quote(str(runtime))}
ip() {{ echo 'sandbox-writer (id: 1)'; }}
prepare_network
'''
        self.assertEqual(self.shell(command).returncode, 0)
        self.load([{"path": str(self.project), "apps": ["writer"], "endpoints": ["new.example"]}])
        result = self.shell(command)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("installed policy is stale", result.stderr)

    def test_host_proxy_generation_uses_combined_endpoints_and_fingerprint(self):
        data = self.load([{"path": str(self.project), "apps": ["writer"],
                           "endpoints": ["project.example"]}])
        runtime = self.root / "proxy"
        result = run_bash(f'''source {shlex.quote(str(ROOT / 'host/up'))}
CONFIG={shlex.quote(str(self.public))}; LOCAL_CONFIG={shlex.quote(str(self.private))}
PROXY_DIR={shlex.quote(str(runtime))}; POOL_BASE=10.77.0
cp() {{ :; }}
systemctl() {{ :; }}
install_proxy
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = json.loads((runtime / "apps.json").read_text())
        self.assertEqual(installed["policy_fingerprint"], data["policy_fingerprint"])
        self.assertEqual(installed["apps"][0]["endpoints"], ["base.example", "project.example"])

    def test_private_symlink_target_is_protected(self):
        data = self.load([{"path": str(self.project), "apps": ["writer"]}])
        link = self.root / "private-link.toml"
        link.symlink_to(self.private)
        linked = loader.read_config(self.public, link)
        self.assertEqual(linked["config_paths"], data["config_paths"])
        self.assertEqual(linked["policy_fingerprint"], data["policy_fingerprint"])
