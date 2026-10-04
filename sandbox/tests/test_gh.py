"""Shared GitHub state remains accessible only to explicitly granted apps."""
import shlex
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from test_support import ROOT, load_module, run_bash, write_config

config_reader = load_module("sandbox_gh_config", ROOT / "lib/load_config.py")


class GithubStateTests(unittest.TestCase):
    def test_github_commands_share_config_and_wrappers_forward_arguments(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config_reader, "user_home", return_value=directory):
            profiles = [app for app in config_reader.read_config(ROOT / "sandbox.toml", ROOT / "tests/absent_local.toml")["apps"]
                        if app["name"] in ("gh", "codex", "opencode")]
            self.assertEqual(len(profiles), 3)
            config = Path(directory) / "config.toml"
            write_config(config, {"apps": profiles})
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            sudo = bin_dir / "sudo"
            sudo.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\n')
            sudo.chmod(0o755)
            for app in profiles:
                with self.subTest(app=app["name"]):
                    command = app["cmd"]
                    self.assertIn(f"GH_CONFIG_DIR={directory}/.local/share/sandbox/gh", command)
                    self.assertIn("GH_NO_UPDATE_NOTIFIER=1", command)
                    self.assertEqual(app["dir"]["state"], [f"{directory}/.local/share/sandbox/gh"])
                    self.assertTrue({"github.com", "api.github.com"} <= set(app["endpoints"]))
                    result = run_bash(f'''source {shlex.quote(str(ROOT / "bin/sandbox_wrappers"))}
HOME={shlex.quote(directory)}; CONFIG={shlex.quote(str(config))}
BIN_DIR={shlex.quote(str(bin_dir))}; BACKUP_DIR="$HOME/backups"; LAUNCHER='/sandbox launcher'
write_wrapper {app["name"]} >/dev/null
export PATH="$BIN_DIR:$PATH"
bash "$BIN_DIR/{app["name"]}" --version 'argument with spaces'
''')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.rstrip("\0").split("\0"),
                                     ["-n", "/sandbox launcher", "--app", app["name"], *command,
                                      "--version", "argument with spaces"])

    def test_shared_state_is_granted_and_unrelated_state_stays_private(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            shared, private = home / "gh", home / "codex"
            shared.mkdir()
            private.mkdir()
            config = home / "config.toml"
            write_config(config, {"apps": [
                {"name": "gh", "dir.state": [str(shared)]},
                {"name": "codex", "dir.state": [str(shared)], "codex_home": str(private)},
                {"name": "opencode", "dir.state": [str(shared)]},
                {"name": "other"},
            ]})
            source = f'''source {shlex.quote(str(ROOT / "bin/sandbox"))}
source {shlex.quote(str(ROOT / "lib/render_apparmor.sh"))}
CONFIG={shlex.quote(str(config))}
'''
            for app in ("gh", "codex", "opencode", "other"):
                with self.subTest(app=app):
                    result = run_bash(source + f'''APP={app}
build_mask_args {shlex.quote(directory)}
printf '%s\\n' "${{MASK_ARGS[@]}}"
app_file_rules {app} {shlex.quote(directory)}
''')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if app == "other":
                        self.assertIn(str(shared), result.stdout.splitlines())
                        self.assertIn(f'deny "{shared}/**" rwklmx,', result.stdout)
                    else:
                        self.assertNotIn(str(shared), result.stdout.splitlines())
                        self.assertNotIn(f'deny "{shared}/**"', result.stdout)
                        self.assertIn(f'"{shared}/**" rwklmix,', result.stdout)
                    if app != "codex":
                        self.assertIn(f'deny "{private}/**" rwklmx,', result.stdout)

    def test_readonly_grant_does_not_conflict_with_private_state_denial(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            write_config(config, {"apps": [
                {"name": "owner", "dir.state": [directory]},
                {"name": "reader", "dir.read": [directory]},
            ]})
            result = run_bash(f'''source {shlex.quote(str(ROOT / "lib/query_config.sh"))}
source {shlex.quote(str(ROOT / "lib/render_apparmor.sh"))}
CONFIG={shlex.quote(str(config))}
app_file_rules reader /project
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f'"{directory}/**" rmk,', result.stdout)
            self.assertIn(f'deny "{directory}/**" wl,', result.stdout)
            self.assertNotIn(f'deny "{directory}/**" rwklmx,', result.stdout)
