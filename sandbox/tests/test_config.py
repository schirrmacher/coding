"""TOML loading and per-app state permissions."""
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_support import isolated_environment, ROOT, load_module, write_config

config_reader = load_module("sandbox_config", ROOT / "lib/load_config.py")


def query(path, command):
    script = f'''set -euo pipefail
source {shlex.quote(str(ROOT / 'lib/query_config.sh'))}
source {shlex.quote(str(ROOT / 'lib/render_apparmor.sh'))}
CONFIG={shlex.quote(str(path))}
{command}
'''
    return subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())


def bash(functions, command):
    script = "set -euo pipefail\n" + functions + "\n" + command
    return subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())


class ConfigTests(unittest.TestCase):
    def test_every_app_denies_config_writes_even_inside_writable_project(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            config = path / "sandbox.toml"
            apps = ["orca", "claude", "codex", "vscode", "opencode", "future-app"]
            write_config(config, {"apps": [{"name": app, "dir.write": [directory]} for app in apps]})
            link = path / "config-link.toml"
            link.symlink_to(config)
            for app in apps:
                with self.subTest(app=app):
                    result = query(link, f"app_file_rules {app} {shlex.quote(directory)}")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(f'"{config}" r,', result.stdout)
                    self.assertIn(f'deny "{config}" wkl,', result.stdout)
                    self.assertIn(f'"{path}/**" rwklmix,', result.stdout)
            original = config.read_bytes()
            config.write_bytes(original + b"\n# host edit\n")
            self.assertTrue(config.read_bytes().endswith(b"# host edit\n"))

    def test_shipped_config_and_codex_home(self):
        data = config_reader.read_config(ROOT / "sandbox.toml", ROOT / "tests/absent_local.toml")
        self.assertEqual(data["default"], "orca")
        self.assertEqual([app["name"] for app in data["apps"]],
                         ["orca", "claude", "codex", "vscode", "opencode", "gh", "cargo", "uv"])
        codex = next(app for app in data["apps"] if app["name"] == "codex")
        self.assertEqual(codex["codex_home"], str(Path(config_reader.user_home()) / ".codex"))
        self.assertIn(str(Path(config_reader.user_home()) / ".agents"), codex["dir"]["read"])

    def test_toml_comments_and_missing_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            config.write_text(
                '# comment\n'
                'default = "demo"\n'
                '[[apps]]\n'
                'name = "demo"\n'
                'endpoints = ["example.com"]\n'
            )
            result = query(config, f"app_project_directories demo {shlex.quote(directory)}")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")

    def test_nested_dir_table_and_empty_read_list(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            write_config(config, {"apps": [{"name": "demo", "dir": {
                "write": [directory], "read": [],
            }}]})
            result = query(config, f"app_writable_directories demo {shlex.quote(directory)}")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [directory])
            result = query(config, "app_readable_directories demo")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")

    def test_invalid_directory_schema_is_rejected_by_every_config_reader(self):
        invalid = [
            ({"directories": ["/project"]}, "use dir.write"),
            ({"readable_directories": ["/skills"]}, "use dir.read"),
            ({"dir": "invalid"}, "dir must be a table"),
            ({"dir": {"execute": ["/bin"]}}, "only read, write, and state"),
            ({"dir.write": []}, "dir.write"),
            ({"dir.write": "/project"}, "dir.write"),
            ({"dir.write": [1]}, "dir.write"),
            ({"dir.write": ["relative"]}, "absolute paths"),
            ({"dir.read": "/skills"}, "dir.read"),
            ({"dir.read": [""]}, "dir.read"),
            ({"dir.read": ["relative"]}, "absolute paths"),
            ({"dir.state": "/state"}, "dir.state"),
            ({"dir.state": [1]}, "dir.state"),
            ({"dir.state": [""]}, "dir.state"),
            ({"dir.state": ["relative"]}, "absolute paths"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            for settings, message in invalid:
                with self.subTest(settings=settings):
                    write_config(config, {"apps": [{"name": "demo", **settings}]})
                    result = query(config, "read_config")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(message, result.stderr)

    def test_up_rejects_unsupported_network_and_ports(self):
        functions = "source " + shlex.quote(str(ROOT / "host/up"))
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            data = {
                "default": "demo",
                "apps": [
                    {
                        "name": "demo",
                        "dir.write": None,
                        "endpoints": ["example.com"],
                    },
                ],
                "net": {"subnet": "10.77.0.0/24"},
                "proxy": {"sni_port": 3128, "dns_port": 53},
            }
            network_cases = [
                ("10.77.0.0/24", 3128, 53, True),
                ("10.77.0.0/16", 3128, 53, False),
                ("999.77.0.0/24", 3128, 53, False),
                ("10.77.0.0/24", 1.5, 53, False),
                ("10.77.0.0/24", 3128, 54, False),
            ]
            for subnet, port, dns, valid in network_cases:
                with self.subTest(subnet=subnet, port=port, dns=dns):
                    data["net"]["subnet"] = subnet
                    data["proxy"] = {"sni_port": port, "dns_port": dns}
                    write_config(config, data)
                    result = bash(functions, f"CONFIG={str(config)!r}; DEFAULT_PROJECT_DIRECTORY={directory!r}; load_config")
                    self.assertEqual(result.returncode == 0, valid, result.stderr)


    def test_up_rejects_missing_and_nested_writable_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            child = path / "child"
            child.mkdir()
            config = path / "config.toml"
            invalid = [
                ({"dir.write": [str(path / "missing")]}, "does not exist"),
                ({"dir.read": [str(path / "missing")]}, "does not exist"),
                ({"dir.state": [str(path / "missing")]}, "does not exist"),
                ({"dir.write": [str(path), str(child)]}, "is inside"),
                ({"dir.write": [str(path)], "dir.state": [str(child)]}, "is inside"),
            ]
            for settings, message in invalid:
                with self.subTest(settings=settings):
                    write_config(config, {"apps": [{"name": "demo", **settings}]})
                    script = f'''source {shlex.quote(str(ROOT / "host/up"))}
CONFIG={shlex.quote(str(config))}; DEFAULT_PROJECT_DIRECTORY={shlex.quote(directory)}; APPS=(demo)
validate_app_directories
'''
                    result = subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(message, result.stderr)

    def test_up_creates_persistent_state_as_invoking_user_and_keeps_existing_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            state = path / "new state" / "cargo"
            config = path / "config.toml"
            write_config(config, {"apps": [{"name": "cargo", "dir.state": [str(state)]}]})
            script = f'''source {shlex.quote(str(ROOT / "host/up"))}
CONFIG={shlex.quote(str(config))}; SUDO_UID=1234; SUDO_GID=5678
getent() {{ echo "test:x:1234:5678::/home/test:/bin/bash"; }}
setpriv() {{
    [[ $1 == --reuid=1234 && $2 == --regid=5678 && $3 == --init-groups && $4 == --reset-env ]]
    shift 4
    "$@"
}}
prepare_app_state
'''
            result = subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(state.is_dir())
            marker = state / "keep"
            marker.write_text("existing cache")
            result = subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(marker.read_text(), "existing cache")

    def test_up_bootstraps_uv_runtime_before_readable_directory_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            write_config(config, {"apps": [{"name": "uv", "cmd": ["/usr/bin/env",
                "/home/test/.local/share/sandbox/runtimes/uv/uv"]}]})
            script = f'''source {shlex.quote(str(ROOT / "host/up"))}
CONFIG={shlex.quote(str(config))}; SUDO_UID=1234; SUDO_GID=5678
getent() {{ echo "test:x:1234:5678::/home/test:/bin/bash"; }}
setpriv() {{ printf '%s\\n' "$@"; }}
prepare_app_state
'''
            result = subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines()[:5],
                             ["--reuid=1234", "--regid=5678", "--init-groups", "--reset-env", "python3"])
            self.assertEqual(Path(result.stdout.splitlines()[5]).resolve(), ROOT / "lib/prepare_uv.py")

    def test_symlink_paths_and_overrides_use_the_same_canonical_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            project = path / "project with spaces"
            project.mkdir()
            link = path / "project-link"
            link.symlink_to(project)
            config = path / "config.toml"
            write_config(config, {"apps": [{"name": "demo", "dir.write": [str(link), str(project)],
                                           "dir.read": [str(link), str(project)]}]})
            for command in (f"app_writable_directories demo {shlex.quote(directory)}",
                            "app_readable_directories demo",
                            f"app_writable_directories demo {shlex.quote(directory)} {shlex.quote(str(link))}"):
                with self.subTest(command=command):
                    result = query(config, command)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.splitlines(), [str(project)])

    def test_bad_toml_stops_with_a_readable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            config.write_text('default = [')
            result = query(config, "read_config")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot parse config", result.stderr)
            self.assertIn(str(config), result.stderr)

    def test_codex_state_and_readonly_skills_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            project, state = (path / name for name in ("project", "state with spaces"))
            skills = project / "skills"
            for folder in (project, state, skills):
                folder.mkdir()
            config = path / "config.toml"
            config_data = {
                "apps": [
                    {
                        "name": "codex",
                        "codex_home": str(state),
                        "dir.write": [str(project)],
                        "dir.read": [str(skills)],
                    },
                    {"name": "other"},
                ],
            }
            write_config(config, config_data)
            result = query(config, f"app_writable_directories codex {shlex.quote(str(project))}")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [str(project), str(state)])
            result = query(config, f"app_file_rules codex {shlex.quote(str(project))}")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f'"{state}/**" rwklmix,', result.stdout)
            self.assertIn(f'"{skills}/**" rmk,', result.stdout)
            self.assertNotIn(f'deny "{state}/**"', result.stdout)
            self.assertIn(f'deny "{skills}/**" wl,', result.stdout)
            self.assertNotIn(f'deny "{skills}/**" wkl,', result.stdout)
            result = query(config, f"app_file_rules other {shlex.quote(str(project))}")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f'deny "{state}/**" rwklmx,', result.stdout)

    def test_invalid_state_and_readable_settings_fail_before_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            data = {
                "default": "codex",
                "net": {"subnet": "10.77.0.0/24"},
                "proxy": {"sni_port": 3128, "dns_port": 53},
                "apps": [{"name": "codex", "endpoints": ["example.com"]}],
            }
            invalid_settings = (
                ("codex_home", "relative"),
                ("codex_home", 123),
                ("dir.read", "not an array"),
                ("dir.read", ["relative"]),
            )
            for key, value in invalid_settings:
                with self.subTest(key=key, value=value):
                    data["apps"][0].pop("codex_home", None)
                    data["apps"][0].pop("dir.read", None)
                    data["apps"][0][key] = value
                    write_config(path, data)
                    script = f'''source {shlex.quote(str(ROOT / "host/up"))}
CONFIG={shlex.quote(str(path))}
validate_config
'''
                    result = subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(key, result.stderr)

    def test_directory_override_keeps_codex_state_and_other_apps_mask_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            config = path / "config.toml"
            state, project = path / "state", path / "project"
            state.mkdir()
            project.mkdir()
            config_data = {"apps": [{"name": "codex", "codex_home": str(state), "dir.write": [str(project)]}, {"name": "other"}]}
            write_config(config, config_data)
            source = f"source {shlex.quote(str(ROOT / 'bin/sandbox'))}\nCONFIG={shlex.quote(str(config))}\n"
            script = source + f'''APP=codex; DIRECTORY_ARGS=({shlex.quote(str(project))})
resolve_directories
'''
            result = subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [str(project), str(state)])
            script = source + f'''APP=other
build_mask_args {shlex.quote(str(path))}
printf '%s\\n' "${{MASK_ARGS[@]}}"
'''
            result = subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["--tmpfs", str(state)])

    def test_home_uses_account_record_with_and_without_sudo(self):
        for env, uid in (({}, os.getuid()), ({"SUDO_UID": "1234", "HOME": "/root"}, 1234)):
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True), patch.object(
                    config_reader.pwd, "getpwuid", return_value=SimpleNamespace(pw_dir="/home/two words")) as lookup:
                self.assertEqual(config_reader.user_home(), "/home/two words")
                lookup.assert_called_once_with(uid)

    def test_home_expansion_is_literal_and_rejects_unknown_placeholders(self):
        self.assertEqual(config_reader.expand_home(["${HOME}/bin", "/absolute", "$(touch nope)"], "/home/two words"),
                         ["/home/two words/bin", "/absolute", "$(touch nope)"])
        with self.assertRaisesRegex(ValueError, "only"):
            config_reader.expand_home("${OTHER}/bin", "/home/user")

    def test_loader_expands_every_path_setting_before_shell_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            config_data = {
                "apps": [
                    {
                        "name": "codex",
                        "cmd": ["${HOME}/bin/codex", "literal arg"],
                        "dir.write": ["${HOME}/project"],
                        "codex_home": "${HOME}/.codex",
                        "dir.read": ["${HOME}/skills", "/absolute"],
                    },
                ],
            }
            write_config(config, config_data)
            with patch.object(config_reader, "user_home", return_value="/home/two words"):
                app = config_reader.read_config(config, ROOT / "tests/absent_local.toml")["apps"][0]
            self.assertEqual(app["cmd"], ["/home/two words/bin/codex", "literal arg"])
            self.assertEqual(app["dir"]["write"], ["/home/two words/project"])
            self.assertEqual(app["codex_home"], "/home/two words/.codex")
            self.assertEqual(app["dir"]["read"], ["/home/two words/skills", "/absolute"])
            for value in ("${OTHER}/bin", "${HOME/bin"):
                config_data = {"apps": [{"name": "codex", "cmd": [value]}]}
                write_config(config, config_data)
                result = query(config, "read_config")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("only ${HOME}", result.stderr)
