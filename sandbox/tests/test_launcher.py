"""Payload arguments, environment, mounts, and launch prerequisites."""
import json
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_support import isolated_environment, ROOT, load_module, write_config


def bash(functions, command):
    script = "set -euo pipefail\n" + functions + "\n" + command
    return subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())


class LauncherTests(unittest.TestCase):
    def test_env_values_preserve_equals_and_spaces(self):
        functions = "source " + shlex.quote(str(ROOT / "bin/sandbox"))
        script = '''ENV_ARGS=(); DIRECTORY_ARGS=(); CMD=()
export TEST_VALUE='two words'
parse_args --env TEST_VALUE --env 'TOKEN=a=b c' echo --env untouched
printf '%s\\n' "${ENV_ARGS[@]}" "${CMD[@]}"'''
        result = bash(functions, script)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected_arguments = [
            "--setenv", "TEST_VALUE", "two words",
            "--setenv", "TOKEN", "a=b c",
            "echo", "--env", "untouched",
        ]
        self.assertEqual(result.stdout.splitlines(), expected_arguments)


    def test_payload_preserves_gui_environment_and_mount_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            workspace = path / "work with spaces"
            workspace.mkdir()
            shared = workspace / "shared skills"
            shared.mkdir()
            state = path / "codex state"
            state.mkdir()
            config = path / "config.toml"
            config_data = {
                "apps": [
                    {
                        "name": "demo",
                        "gui": True,
                        "dir.write": [str(workspace)],
                        "codex_home": str(state),
                        "dir.read": [str(shared)],
                    },
                ],
            }
            write_config(config, config_data)
            runtime = path / "runtime.json"
            runtime_data = {"apps": [{"name": "demo", "ip": "10.77.0.1"}], "proxy": {"sni_port": 3128}}
            runtime_data["policy_fingerprint"] = load_module("config_loader", ROOT / "lib/load_config.py").read_config(config, ROOT / "tests/absent_local.toml")["policy_fingerprint"]
            runtime.write_text(json.dumps(runtime_data))
            ip = path / "ip"
            ip.write_text(
                "#!/bin/bash\n"
                "if [[ $2 == list ]]; then\n"
                "    echo 'sandbox-demo (id: 1)'\n"
                "else\n"
                "    printf '%s\\0' \"$@\"\n"
                "fi\n"
            )
            ip.chmod(0o755)
            script = f'''
CONFIG={shlex.quote(str(config))}; PROXY_CONFIG={shlex.quote(str(runtime))}
export PATH={shlex.quote(str(path))}:$PATH DISPLAY=:test WAYLAND_DISPLAY=wayland-test
export XDG_RUNTIME_DIR='/run/user/test session' DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/test/bus'
SUDO_UID=$(id -u); SUDO_GID=$(id -g)
aa-exec() {{ return 0; }}
APP=demo; DIRECTORY_ARGS=(); ENV_ARGS=(); CMD=()
parse_args --env 'EXPLICIT=two words=a=b' echo 'payload argument'
run_payload
'''
            result = bash("source " + shlex.quote(str(ROOT / "bin/sandbox")), script)
            self.assertEqual(result.returncode, 0, result.stderr)
            arguments = result.stdout.rstrip("\0").split("\0")
            self.assertEqual(arguments[:3], ["netns", "exec", "sandbox-demo"])
            self.assertLess(arguments.index("--clearenv"), arguments.index("DISPLAY"))
            display_index = arguments.index("DISPLAY")
            self.assertEqual(arguments[display_index + 1], ":test")
            runtime_index = arguments.index("XDG_RUNTIME_DIR")
            self.assertEqual(arguments[runtime_index + 1], "/run/user/test session")
            session_index = arguments.index("DBUS_SESSION_BUS_ADDRESS")
            self.assertEqual(arguments[session_index + 1], "unix:path=/run/user/test/bus")
            explicit_index = arguments.index("EXPLICIT")
            self.assertEqual(arguments[explicit_index + 1], "two words=a=b")
            self.assertEqual(arguments[-3:], ["--", "echo", "payload argument"])
            self.assertLess(arguments.index("--ro-bind"), arguments.index("--bind"))
            bind_index = arguments.index("--bind")
            self.assertEqual(arguments[bind_index + 1:bind_index + 3], [str(workspace)] * 2)
            home_index = arguments.index("CODEX_HOME")
            self.assertEqual(arguments[home_index + 1], str(state))
            self.assertEqual(arguments[home_index - 1], "--setenv")
            self.assertIn(str(state), arguments)
            self.assertGreater(home_index, arguments.index("--clearenv"))
            readonly_index = arguments.index("--ro-bind", arguments.index("--ro-bind") + 1)
            self.assertEqual(arguments[readonly_index + 1:readonly_index + 3], [str(shared)] * 2)
            self.assertGreater(readonly_index, bind_index)
            config_index = arguments.index(str(config))
            self.assertEqual(arguments[config_index - 1:config_index + 2],
                             ["--ro-bind", str(config), str(config)])
            self.assertGreater(config_index, arguments.index("--bind-try"))


    def test_config_mount_survives_directory_overrides_for_every_app(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            config = path / "config with spaces.toml"
            override = path / "override"
            override.mkdir()
            apps = ["orca", "claude", "codex", "vscode", "opencode", "future-app"]
            write_config(config, {"apps": [{"name": app, "dir.write": [str(override)]} for app in apps]})
            link = path / "config-link.toml"
            link.symlink_to(config)
            for app in apps:
                with self.subTest(app=app):
                    script = f'''
CONFIG={shlex.quote(str(link))}; APP={shlex.quote(app)}
DIRECTORY_ARGS=({shlex.quote(str(override))})
HOME_DIR={shlex.quote(directory)}
mapfile -t DIRECTORIES < <(resolve_directories)
prepare_mounts_and_environment
printf '%s\\n' "$CONFIG_PATH" "${{DIRECTORIES[@]}}"
'''
                    result = bash("source " + shlex.quote(str(ROOT / "bin/sandbox")), script)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.splitlines(), [str(config), str(override)])


    def test_missing_config_stops_launch_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            script = f'CONFIG={shlex.quote(directory + "/missing.toml")}\nprepare_mounts_and_environment\necho unexpected'
            result = bash("source " + shlex.quote(str(ROOT / "bin/sandbox")), script)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("unexpected", result.stdout)


    def test_payload_requires_proxy_config_and_apparmor_unless_explicitly_waived(self):
        functions = "source " + shlex.quote(str(ROOT / "bin/sandbox"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            config = path / "config.toml"
            config_data = {"apps": [{"name": "demo", "dir.write": [directory]}]}
            write_config(config, config_data)
            runtime = path / "runtime.json"
            runtime_data = {
                "apps": [{"name": "demo", "ip": "10.77.0.1"}],
                "proxy": {"sni_port": 3128},
            }
            runtime_data["policy_fingerprint"] = load_module("config_loader", ROOT / "lib/load_config.py").read_config(config, ROOT / "tests/absent_local.toml")["policy_fingerprint"]
            runtime.write_text(json.dumps(runtime_data))

            ip = path / "ip"
            ip.write_text(
                "#!/bin/bash\n"
                "if [[ $2 == list ]]; then\n"
                "    echo 'sandbox-demo (id: 1)'\n"
                "else\n"
                "    printf '%s\\0' \"$@\"\n"
                "fi\n"
            )
            ip.chmod(0o755)

            cases = (
                (path / "missing.json", 0, 1, "proxy config missing"),
                (runtime, 0, 1, "AppArmor profile 'sandbox-demo' not loaded"),
                (runtime, 1, 0, "WARNING: proceeding without the AppArmor profile"),
            )
            for runtime_path, allow_no_apparmor, exit_code, message in cases:
                with self.subTest(runtime=runtime_path.name, waiver=allow_no_apparmor):
                    script = f'''
CONFIG={shlex.quote(str(config))}
PROXY_CONFIG={shlex.quote(str(runtime_path))}
export PATH={shlex.quote(directory)}:$PATH
SUDO_UID=$(id -u)
SUDO_GID=$(id -g)
SANDBOX_ALLOW_NO_APPARMOR={allow_no_apparmor}
aa-exec() {{ return 1; }}
APP=demo
DIRECTORY_ARGS=()
ENV_ARGS=()
CMD=(true)
run_payload
'''
                    result = bash(functions, script)
                    self.assertEqual(result.returncode, exit_code, result.stderr)
                    self.assertIn(message, result.stderr)
                    if exit_code:
                        self.assertEqual(result.stdout, "")
                    else:
                        arguments = result.stdout.rstrip("\0").split("\0")
                        self.assertEqual(arguments[:3], ["netns", "exec", "sandbox-demo"])
                        self.assertNotIn("aa-exec", arguments)
