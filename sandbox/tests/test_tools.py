"""Package-manager state stays private and wrappers preserve installed runtimes."""
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_support import ROOT, load_module, run_bash, write_config

config_reader = load_module("sandbox_tool_config", ROOT / "lib/load_config.py")

class ToolStateTests(unittest.TestCase):
    def test_working_folder_selection_keeps_project_and_private_state_mounts(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            project, override, state = [home / name for name in ("project", "override", "state with spaces")]
            for path in (project, override, state):
                path.mkdir()
            link = home / "state-link"
            link.symlink_to(state)
            config = home / "config.toml"
            write_config(config, {"apps": [
                {"name": "cargo", "dir.write": [str(project)], "dir.state": [str(link), str(state)]},
                {"name": "uv"},
            ]})
            source = f'source {shlex.quote(str(ROOT / "bin/sandbox"))}\nsource {shlex.quote(str(ROOT / "lib/render_apparmor.sh"))}\nCONFIG={shlex.quote(str(config))}\n'
            result = run_bash(source + f'''APP=cargo; HOME_DIR={shlex.quote(directory)}
DIRECTORY_ARGS=({shlex.quote(str(override))})
mapfile -t DIRECTORIES < <(resolve_directories)
prepare_mounts_and_environment
printf '%s\\n' "${{BIND_ARGS[@]}}"
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["--bind", str(project), str(project),
                                                         "--bind", str(state), str(state)])
            result = run_bash(source + f'app_file_rules cargo {shlex.quote(str(project))}')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f'"{state}/**" rwklmix,', result.stdout)
            result = run_bash(source + f'''APP=uv
build_mask_args {shlex.quote(directory)}
printf '%s\\n' "${{MASK_ARGS[@]}}"
app_file_rules uv {shlex.quote(str(project))}
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines()[:2], ["--tmpfs", str(state)])
            self.assertIn(f'deny "{state}/**" rwklmx,', result.stdout)

    def test_tool_profiles_forward_state_environment_and_arguments_without_recursive_wrappers(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config_reader, "user_home", return_value=directory):
            home = Path(directory)
            profiles = [app for app in config_reader.read_config(ROOT / "sandbox.toml")["apps"]
                        if app["name"] in ("cargo", "uv")]
            config = home / "config.toml"
            write_config(config, {"apps": profiles})
            bin_dir = home / ".local/bin"
            bin_dir.mkdir(parents=True)
            sudo = bin_dir / "sudo"
            sudo.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\n')
            sudo.chmod(0o755)
            for app in profiles:
                with self.subTest(app=app["name"]):
                    name = app["name"]
                    command = app["cmd"]
                    result = run_bash(f'''source {shlex.quote(str(ROOT / "bin/sandbox_wrappers"))}
HOME={shlex.quote(directory)}; CONFIG={shlex.quote(str(config))}
BIN_DIR="$HOME/.local/bin"; BACKUP_DIR="$HOME/backups"; LAUNCHER='/sandbox launcher'
write_wrapper {name} >/dev/null
export PATH="$BIN_DIR:$PATH"
bash "$BIN_DIR/{name}" --version 'argument with spaces' '*.rs'
''')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.rstrip("\0").split("\0"),
                                     ["-n", "/sandbox launcher", "--app", name, *command,
                                      "--version", "argument with spaces", "*.rs"])
                    environment = dict(argument.split("=", 1) for argument in command[1:-1])
                    self.assertNotIn(str(bin_dir), environment["PATH"].split(":"))
                    self.assertEqual(app["dir"]["state"], [str(home / ".local/share/sandbox" / name)])
                    if name == "cargo":
                        self.assertEqual(environment["RUSTUP_AUTO_INSTALL"], "0")
                        self.assertEqual(environment["CARGO_HOME"], app["dir"]["state"][0])
                        self.assertEqual(environment["CARGO_REGISTRIES_CRATES_IO_PROTOCOL"], "sparse")
                    else:
                        for key in ("UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR", "UV_PYTHON_BIN_DIR",
                                    "UV_TOOL_DIR", "UV_TOOL_BIN_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
                            self.assertTrue(Path(environment[key]).is_relative_to(app["dir"]["state"][0]))
