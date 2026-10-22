"""SIGRID runtime and desktop bus access stay confined to opted-in apps."""
import shlex
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_support import ROOT, load_module, run_bash, write_config

setup = load_module("prepare_sigrid", ROOT / "lib/prepare_sigrid.py")
loader = load_module("sigrid_config", ROOT / "lib/load_config.py")


class SigridTests(unittest.TestCase):
    def test_runtime_uses_installed_package_without_changing_host_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            package = home / ".local/share/sigrid/sigrid"
            package.mkdir(parents=True)
            (package / "__init__.py").touch()
            (package / "cli.py").write_text(
                'import sys\ndef main():\n    print("SIGRID test help", *sys.argv[1:])\n    return 0\n')
            original = home / ".local/bin/sigrid"
            original.parent.mkdir(parents=True)
            original.write_text("keep host launcher")
            launcher = setup.prepare_sigrid(home)
            self.assertEqual(setup.prepare_sigrid(home), launcher)
            result = subprocess.run([str(launcher), "--help"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "SIGRID test help --help\n")
            self.assertEqual(original.read_text(), "keep host launcher")

    def test_missing_installation_does_not_create_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "not installed"):
                setup.prepare_sigrid(directory)
            self.assertFalse((Path(directory) / ".local/share/sandbox").exists())

    def test_local_config_can_disable_sigrid_and_rejects_non_boolean_values(self):
        with tempfile.TemporaryDirectory() as directory:
            public, local = Path(directory) / "public.toml", Path(directory) / "local.toml"
            write_config(public, {"apps": [{"name": "codex", "sigrid": True}]})
            write_config(local, {"apps": [{"name": "codex", "sigrid": False}]})
            self.assertFalse(loader.read_config(public, local)["apps"][0]["sigrid"])
            for value in ("true", 1, []):
                with self.subTest(value=value):
                    write_config(local, {"apps": [{"name": "codex", "sigrid": value}]})
                    with self.assertRaisesRegex(ValueError, "sigrid must be true or false"):
                        loader.read_config(public, local)

    def test_secret_service_policy_is_only_granted_to_enabled_apps(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            write_config(config, {"apps": [{"name": "enabled", "sigrid": True}, {"name": "disabled"}]})
            for name in ("enabled", "disabled"):
                with self.subTest(app=name):
                    result = run_bash(f'''source {shlex.quote(str(ROOT / "lib/query_config.sh"))}
source {shlex.quote(str(ROOT / "lib/render_apparmor.sh"))}
CONFIG={shlex.quote(str(config))}
app_sigrid_rules {name}
''')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if name == "enabled":
                        self.assertIn("peer=(name=org.freedesktop.secrets)", result.stdout)
                        self.assertIn("owner /run/user/*/bus rw", result.stdout)
                    else:
                        self.assertEqual(result.stdout, "")

    def test_bus_mount_exposes_only_socket_and_preserves_codex_environment(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket(socket.AF_UNIX) as bus:
            path = Path(directory) / "bus"
            bus.bind(str(path))
            result = run_bash(f'''source {shlex.quote(str(ROOT / "bin/sandbox"))}
READ_ARGS=(); APP_ENV_ARGS=(--setenv CODEX_HOME '/codex state')
build_sigrid_args {shlex.quote(str(path))}
printf '%s\\n' "${{READ_ARGS[@]}}" "${{APP_ENV_ARGS[@]}}"
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["--ro-bind", str(path), str(path),
                "--setenv", "CODEX_HOME", "/codex state", "--setenv", "DBUS_SESSION_BUS_ADDRESS", f"unix:path={path}"])

    def test_missing_desktop_bus_reports_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_bash(f'''source {shlex.quote(str(ROOT / "bin/sandbox"))}
READ_ARGS=(); APP_ENV_ARGS=()
build_sigrid_args {shlex.quote(str(Path(directory) / "missing-bus"))}
''')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SIGRID or browser access requires the desktop session bus", result.stderr)
