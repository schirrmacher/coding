"""Managed command wrappers and generated desktop entries."""
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_support import isolated_environment, ROOT, write_config


def bash(functions, command):
    script = "set -euo pipefail\n" + functions + "\n" + command
    return subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())


class WrapperTests(unittest.TestCase):
    def test_wrapper_preserves_command_and_forwarded_arguments(self):
        functions = "source " + shlex.quote(str(ROOT / "bin/sandbox_wrappers"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            config = path / "config.toml"
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
                *command, "forwarded value",
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
            config = path / "config.toml"
            config_data = {"apps": [{"name": "codex", "cmd": [str(executable)]}]}
            write_config(config, config_data)
            source = "source " + shlex.quote(str(ROOT / "bin/sandbox_wrappers"))
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
                config = path / "config.toml"
                config_data = {"apps": [{"name": "codex", "cmd": [str(executable)]}]}
                write_config(config, config_data)
                script = f'''
CONFIG={shlex.quote(str(config))}; BIN_DIR={shlex.quote(directory)}; BACKUP_DIR="$BIN_DIR/backups"
write_wrapper codex
'''
                result = bash("source " + shlex.quote(str(ROOT / "bin/sandbox_wrappers")), script)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(launcher.is_symlink(), conflict)
                if not conflict:
                    self.assertEqual(launcher.read_text(), "unmanaged launcher")


    def test_wrapper_propagates_sudo_failure_without_running_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            config = path / "config.toml"
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
            result = bash("source " + shlex.quote(str(ROOT / "bin/sandbox_wrappers")), script)
            self.assertEqual(result.returncode, 23)


    def test_desktop_entry_without_original_uses_defaults(self):
        functions = "source " + shlex.quote(str(ROOT / "bin/sandbox_wrappers"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            config = path / "config.toml"
            config_data = {"apps": [{"name": "demo", "cmd": ["/nonexistent app", "two words"]}]}
            write_config(config, config_data)
            script = f'''CONFIG={str(config)!r}; DESKTOP_DIR={directory!r}
LAUNCHER='/sandbox launcher'; MARKER=sandbox-managed
source_desktop_entry() {{ return 0; }}
write_desktop_entry demo'''
            result = bash(functions, script)
            self.assertEqual(result.returncode, 0, result.stderr)
            entry = (path / "demo-sandboxed.desktop").read_text()
            self.assertIn("Name=Demo (sandboxed)", entry)
            self.assertIn('Exec=sudo "/sandbox launcher" "--app" "demo" "/nonexistent app" "two words" %U', entry)
