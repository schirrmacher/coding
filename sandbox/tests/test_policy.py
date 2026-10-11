"""An ordinary app can use the shared policy and launcher APIs through TOML alone."""
import json
import shlex
import copy
import tempfile
import unittest
from pathlib import Path
from test_support import ROOT, load_module, run_bash, write_config

loader = load_module("policy_loader", ROOT / "lib/load_config.py")
runtime = load_module("runtime_preparation", ROOT / "lib/prepare_runtime.py")


class DeclarativePolicyTests(unittest.TestCase):
    def test_new_app_uses_metadata_environment_and_cli_overrides(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public, local = root / "public.toml", root / "local.toml"
            template = root / "original.desktop"
            template.write_text('[Desktop Entry]\nName=Original\nExec=/old %F\nIcon=old\n'
                                '[Desktop Action New]\nName=New\nExec=/old --new %U\n')
            write_config(public, {"apps": [{"name": "drawing", "cmd": ["/bin/echo", "literal=value", "two words"],
                "gui": True, "pty": True, "endpoints": [], "dir": {"write": [str(root)]},
                "env": {"SETTING": "public", "KEPT": "with spaces=and equals"},
                "desktop": {"id": "org.example.Drawing.desktop", "name": "Drawing", "icon": "drawing",
                            "window_class": "org.example.Drawing", "template": str(template)}}]})
            write_config(local, {"apps": [{"name": "drawing", "env": {"SETTING": "local"},
                                         "desktop": {"name": "My Drawing"}}]})
            data = loader.read_config(public, local)
            self.assertEqual(data["apps"][0]["cmd"], ["/bin/echo", "literal=value", "two words"])
            self.assertEqual(data["apps"][0]["env"]["SETTING"], "local")
            script = f'''source {shlex.quote(str(ROOT / "bin/sandbox_wrappers"))}
CONFIG={shlex.quote(str(public))}; LOCAL_CONFIG={shlex.quote(str(local))}
BIN_DIR={shlex.quote(str(root / "bin"))}; DESKTOP_DIR={shlex.quote(str(root / "desktop"))}
BACKUP_DIR={shlex.quote(str(root / "backups"))}; DESKTOP_BACKUP_DIR={shlex.quote(str(root / "desktop-backups"))}
mkdir -p "$BIN_DIR" "$DESKTOP_DIR"
read_config; validate_launcher_config
write_wrapper drawing; write_desktop_entry drawing
'''
            first = run_bash(script)
            self.assertEqual(first.returncode, 0, first.stderr)
            entry = root / "desktop/org.example.Drawing.desktop"
            snapshot = entry.read_bytes()
            self.assertIn('Name=My Drawing', snapshot.decode())
            self.assertIn('StartupWMClass=org.example.Drawing', snapshot.decode())
            self.assertIn(f'Exec="{root}/bin/drawing" --new %U', snapshot.decode())
            self.assertEqual(run_bash(script).returncode, 0)
            self.assertEqual(entry.read_bytes(), snapshot)
            result = run_bash(f'''source {shlex.quote(str(ROOT / "bin/sandbox"))}
CONFIG={shlex.quote(str(public))}; LOCAL_CONFIG={shlex.quote(str(local))}; APP=drawing
CMD=(/bin/echo 'literal=value' 'two words'); ENV_ARGS=(--setenv SETTING cli)
DIRECTORY_ARGS=(); SUDO_UID=$(id -u); SUDO_GID=$(id -g)
prepare_directories; prepare_mounts_and_environment
NS=sandbox-drawing; PROXY_HOST=10.77.0.1; PROXY_PORT=3128; AA_EXEC=(aa-exec -p sandbox-drawing --)
build_launch_command
printf '%s\\0' "${{LAUNCH_COMMAND[@]}}"
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            arguments = result.stdout.rstrip("\0").split("\0")
            settings = [arguments[i + 2] for i, arg in enumerate(arguments[:-2])
                        if arg == "--setenv" and arguments[i + 1] == "SETTING"]
            self.assertEqual(settings, ["local", "cli"])
            self.assertIn("--unshare-net", arguments)
            self.assertEqual(arguments[-3:], ["/bin/echo", "literal=value", "two words"])
            self.assertGreater(arguments.index(str(public)), arguments.index("--bind"))

    def test_terminal_launcher_installs_official_logo_and_preserves_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            state = home / "state"
            state.mkdir()
            marker = state / "keep"
            marker.write_text("existing agent state")
            data = {"apps": [{"name": "herdr", "cmd": ["/bin/true"], "dir": {"state": [str(state)]}}]}
            original = copy.deepcopy(data)
            for _ in range(2):
                runtime.prepare_runtime(data, home)
                icon = home / ".local/share/icons/hicolor/scalable/apps/herdr.svg"
                self.assertEqual(icon.read_bytes(), (ROOT / "assets/herdr.svg").read_bytes())
                service = home / ".local/share/dbus-1/services/dev.herdr.Herdr.service"
                self.assertIn("Name=dev.herdr.Herdr\n", service.read_text())
                self.assertIn("--app-id=dev.herdr.Herdr", service.read_text())
                self.assertEqual(marker.read_text(), "existing agent state")
                self.assertEqual(data, original)

    def test_status_counts_enforcing_kernel_profiles(self):
        with tempfile.TemporaryDirectory() as temporary:
            profiles = Path(temporary) / "profiles"
            profiles.write_text("sandbox-first (enforce)\nsandbox-second (complain)\n")
            result = run_bash(f'source {shlex.quote(str(ROOT / "bin/sandbox"))}\n'
                              f'APPARMOR_PROFILES={shlex.quote(str(profiles))}\n'
                              'print_apparmor_status first second')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "apparmor: 1/2 profiles loaded\n")

    def test_schema_rejects_invalid_extension_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            public = Path(temporary) / "public.toml"
            for fields, message in [({"env": {"BAD-NAME": "x"}}, "env"),
                                    ({"env": {"GOOD": 1}}, "env"),
                                    ({"desktop": {"id": "../wrong.desktop"}}, "desktop.id"),
                                    ({"desktop": {"terminal": "true"}}, "terminal"),
                                    ({"pty": 1}, "pty")]:
                with self.subTest(fields=fields):
                    write_config(public, {"apps": [{"name": "drawing", **fields}]})
                    with self.assertRaisesRegex(ValueError, message):
                        loader.read_config(public, Path(temporary) / "absent.toml")
