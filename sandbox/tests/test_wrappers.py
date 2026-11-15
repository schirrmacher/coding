"""Managed command wrappers and generated desktop entries."""
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_support import isolated_environment, ROOT, write_config


def bash(functions, command):
    script = "set -euo pipefail\n" + functions + "\n" + command
    return subprocess.run(["bash", "--noprofile", "--norc", "-c", script], text=True, capture_output=True, env=isolated_environment())


class WrapperTests(unittest.TestCase):
    def test_installation_skips_non_linux_before_loading_config(self):
        source = "source " + shlex.quote(str(ROOT / "install"))
        script = '''
uname() { echo Darwin; }
read_config() { echo 'unexpected configuration read' >&2; return 1; }
prepare_installation() { echo 'unexpected runtime preparation' >&2; return 1; }
generate_launchers() { echo 'unexpected launcher write' >&2; return 1; }
CONFIG=/nonexistent/definitions
main
'''
        result = bash(source, script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Skipping sandbox wrappers: Linux required\n")
        self.assertEqual(result.stderr, "")

    def test_linux_installation_reaches_existing_flow(self):
        source = "source " + shlex.quote(str(ROOT / "install"))
        script = '''
uname() { echo Linux; }
CONFIG="$SANDBOX_ROOT"
read_config() { echo read_config; }
validate_launcher_config() { echo validate_launcher_config; }
prepare_installation() { echo prepare_installation; }
generate_launchers() { echo generate_launchers; }
remove_stale_launchers() { echo remove_stale_launchers; }
install_host_integration() { echo install_host_integration; }
main
'''
        result = bash(source, script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "read_config", "validate_launcher_config", "prepare_installation",
            "generate_launchers", "remove_stale_launchers", "install_host_integration",
        ])

    def test_wrapper_preserves_command_and_forwarded_arguments(self):
        functions = "source " + shlex.quote(str(ROOT / "install"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            config = path
            command = ["/path with spaces/tool", "two words", "*.py", "a=b"]
            config_data = {"apps": [{"name": "demo", "cmd": command}]}
            write_config(config, config_data)
            sudo = path / "sudo"
            sudo.write_text("#!/bin/bash\nprintf '%s\\n' \"$@\"\n")
            sudo.chmod(0o755)
            script = f'''CONFIG={str(config)!r}; BIN_DIR={directory!r}
LAUNCHER='/sandbox path/launcher'; MARKER=sandbox-managed
write_wrapper demo
export PATH="$BIN_DIR:$PATH"
bash "$BIN_DIR/demo" 'forwarded value' '''
            result = bash(functions, script)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected_arguments = [
                "-n", "/sandbox path/launcher", "--app", "demo",
                "/bin/sh", str(path / "apps/demo/launch.sh"), "forwarded value",
            ]
            self.assertEqual(result.stdout.splitlines()[1:], expected_arguments)
            wrapper = (path / "demo").read_text()
            self.assertTrue(wrapper.startswith("#!/usr/bin/env bash\n"))
            self.assertIn("sandbox-managed", wrapper)


    def test_wrapper_preserves_symlink_and_regeneration_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            executable = path / "real codex"
            executable.write_text("#!/bin/bash\nexit 0\n")
            executable.chmod(0o755)
            (path / "codex").symlink_to(executable)
            config = path
            config_data = {"apps": [{"name": "codex", "cmd": [str(executable)]}]}
            write_config(config, config_data)
            source = "source " + shlex.quote(str(ROOT / "install"))
            script = f'''CONFIG={shlex.quote(str(config))}; BIN_DIR={shlex.quote(directory)}
BACKUP_DIR="$BIN_DIR/backups"
write_wrapper codex
write_wrapper codex
'''
            result = bash(source, script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((path / "codex").is_symlink())
            self.assertEqual((path / "backups/codex").readlink(), executable)


    def test_wrapper_refuses_unmanaged_launcher_and_conflicting_backup(self):
        for conflict in (False, True):
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                executable = path / "real codex"
                executable.write_text("original binary")
                launcher = path / "codex"
                if conflict:
                    launcher.symlink_to(executable)
                    (path / "backups").mkdir()
                    (path / "backups/codex").symlink_to("/unexpected")
                else:
                    launcher.write_text("unmanaged launcher")
                config = path
                config_data = {"apps": [{"name": "codex", "cmd": [str(executable)]}]}
                write_config(config, config_data)
                script = f'''
CONFIG={shlex.quote(str(config))}; BIN_DIR={shlex.quote(directory)}; BACKUP_DIR="$BIN_DIR/backups"
write_wrapper codex
'''
                result = bash("source " + shlex.quote(str(ROOT / "install")), script)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(launcher.is_symlink(), conflict)
                if not conflict:
                    self.assertEqual(launcher.read_text(), "unmanaged launcher")


    def test_wrapper_propagates_sudo_failure_without_running_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            config = path
            config_data = {"apps": [{"name": "demo", "cmd": ["/bin/true"]}]}
            write_config(config, config_data)
            sudo = path / "sudo"
            sudo.write_text("#!/bin/bash\nexit 23\n")
            sudo.chmod(0o755)
            script = f'''
CONFIG={shlex.quote(str(config))}; BIN_DIR={shlex.quote(directory)}
write_wrapper demo
export PATH="$BIN_DIR:$PATH"
"$BIN_DIR/demo"
'''
            result = bash("source " + shlex.quote(str(ROOT / "install")), script)
            self.assertEqual(result.returncode, 23)


    def test_native_desktop_entry_keeps_metadata_and_routes_exec_through_wrapper(self):
        from test_support import native_config
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            config = native_config(path, {"demo": {
                "launch.sh": '#!/bin/sh\nexec /bin/echo "$@"\n',
                "org.example.Demo.desktop": '[Desktop Entry]\nType=Application\nName=Demo\nExec=demo %U\nIcon=demo\n'}})
            result = bash("source " + shlex.quote(str(ROOT / "install")), f'''CONFIG={shlex.quote(str(config))}
DESKTOP_DIR={shlex.quote(str(path))}; BIN_DIR={shlex.quote(str(path / 'bin'))}
write_desktop_entry demo
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            entry = (path / "org.example.Demo.desktop").read_text()
            self.assertIn("Name=Demo", entry)
            self.assertIn(f'Exec="{path}/bin/demo" %U', entry)
