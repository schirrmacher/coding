"""Launch plans preserve native argument order and final protection layers."""
import json
import shlex
import tempfile
import unittest
from pathlib import Path
from test_support import ROOT, load_module, native_config, run_bash

loader = load_module("launch_native_loader", ROOT / "lib/read_definitions.py")


class LauncherTests(unittest.TestCase):
    def test_env_values_preserve_equals_spaces_and_option_like_values(self):
        result = run_bash(f'''source {shlex.quote(str(ROOT / 'bin/sandbox'))}
ENV_ARGS=(); DIRECTORY_ARGS=(); CMD=()
parse_args --env 'TOKEN=a=b c' --env 'LITERAL=--setenv' echo --env untouched
printf '%s\\0' "${{ENV_ARGS[@]}}" "${{CMD[@]}}"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split("\0")[:-1], ["--setenv", "TOKEN", "a=b c", "--setenv", "LITERAL", "--setenv", "echo", "--env", "untouched"])

    def test_native_mounts_precede_masks_and_protected_definitions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            state.mkdir()
            path = native_config(root / "sandbox.toml", {
                "demo": {"mounts.args": f"--bind\n{root}\n{root}\n--setenv\nTOKEN\napp-value\n"},
                "other": {"state": str(state)}})
            result = run_bash(f'''source {shlex.quote(str(ROOT / 'bin/sandbox'))}
CONFIG={shlex.quote(str(path))}; APP=demo; HOME_DIR={shlex.quote(str(root))}
CMD=(/bin/echo 'two words'); ENV_ARGS=(--setenv TOKEN cli-value --setenv LITERAL --setenv)
prepare_mounts_and_environment
NS=sandbox-demo; SUDO_UID=$(id -u); SUDO_GID=$(id -g); WORKING_DIRECTORY=/tmp
DIRECTORIES=(); PROXY_HOST=10.77.0.1; PROXY_PORT=3128; AA_EXEC=()
build_launch_command
printf '%s\\0' "${{LAUNCH_COMMAND[@]}}"
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            args = result.stdout.split("\0")[:-1]
            self.assertIn("--unshare-net", args)
            bind = args.index("--bind")
            self.assertEqual(args[bind + 1:bind + 3], [str(root)] * 2)
            mask = next(index for index in range(len(args) - 1) if args[index:index + 2] == ["--tmpfs", str(state)])
            config = args.index(str(path))
            self.assertLess(bind, mask)
            self.assertLess(mask, config)
            self.assertEqual(args[-3:], ["--", "/bin/echo", "two words"])
            self.assertEqual(args[args.index("SANDBOX_ENV_OVERRIDES") + 1], "TOKEN:LITERAL")
            values = [args[index + 2] for index in range(len(args) - 2) if args[index:index + 2] == ["--setenv", "TOKEN"]]
            self.assertEqual(values, ["app-value", "cli-value"])

    def test_x11_file_shares_ipc_only_when_display_is_present(self):
        for enabled, display in ((True, ":0"), (True, ""), (False, ":0")):
            with self.subTest(enabled=enabled, display=display), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                files = {"mounts.x11.args": ""} if enabled else {}
                path = native_config(root / "sandbox.toml", {"demo": files})
                result = run_bash(f'''source {shlex.quote(str(ROOT / 'bin/sandbox'))}
CONFIG={shlex.quote(str(path))}; APP=demo; HOME_DIR={shlex.quote(str(root))}
DISPLAY={shlex.quote(display)}; CMD=(); ENV_ARGS=()
prepare_mounts_and_environment
printf '%s' "${{IPC_ARGS[*]}}"
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "" if enabled and display else "--unshare-ipc")

    def test_launch_script_wraps_custom_commands_but_not_its_own_default_invocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root / "sandbox.toml", {"demo": {"launch.sh": '#!/bin/sh\nexec "$@"\n'}})
            script = str(root / "apps/demo/launch.sh")
            for command, expected in (("CMD=()", ["/bin/sh", script]),
                                      ("CMD=(echo 'two words')", ["/bin/sh", script, "--sandbox-command", "echo", "two words"]),
                                      (f'CMD=(/bin/sh {shlex.quote(script)} --help)', ["/bin/sh", script, "--help"])):
                result = run_bash(f'''source {shlex.quote(str(ROOT / 'bin/sandbox'))}
CONFIG={shlex.quote(str(path))}; APP=demo; HOME_DIR={shlex.quote(str(root))}; ENV_ARGS=()
{command}
prepare_mounts_and_environment
printf '%s\\0' "${{CMD[@]}}"
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.split("\0")[:-1], expected)

    def test_launch_refuses_stale_installed_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root / "sandbox.toml", {"demo": {}})
            runtime = root / "apps.json"
            runtime.write_text(json.dumps({"policy_fingerprint": "stale", "apps": []}))
            result = run_bash(f'''source {shlex.quote(str(ROOT / 'bin/sandbox'))}
CONFIG={shlex.quote(str(path))}; PROXY_CONFIG={shlex.quote(str(runtime))}; APP=demo
ip() {{ echo "sandbox-demo (id: 1)"; }}
prepare_network
''')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("installed policy is stale", result.stderr)
