"""Runner contracts use temporary fixtures and mocked host commands."""
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_support import isolated_environment, ROOT, load_module, write_config

RUNNER = ROOT / "tests/test_sandbox.sh"
probe = load_module("boundary_probe", ROOT / "tests/boundary/boundary_probe.py")


def shell(script):
    return subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=isolated_environment())


class RunnerTests(unittest.TestCase):
    def run_main(self, args="", overrides="", config=None):
        script = f"source {shlex.quote(str(RUNNER))}\n"
        script += "local_checks() { echo 'local checks'; return 0; }\n"
        script += "installed_checks() { printf 'apps:%s\\n' \"${APPS[*]}\"; return 0; }\n"
        if config:
            script += f"CONFIG={shlex.quote(str(config))}\n"
        return shell(script + overrides + f"\nmain {args}")

    def test_help_and_invalid_options(self):
        result = subprocess.run([str(RUNNER), "--help"], text=True, capture_output=True, cwd="/tmp")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Exit: 0", result.stdout)
        for args in ("--unknown", "--app", "--app demo", "--installed --app 'bad/name'"):
            with self.subTest(args=args):
                self.assertEqual(self.run_main(args).returncode, 2)

    def test_missing_command_is_a_prerequisite_error(self):
        result = self.run_main(overrides="command() { return 1; }")
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing prerequisite: python3", result.stderr)

    def test_local_failure_propagates(self):
        result = self.run_main(overrides="local_checks() { return 1; }")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL sandbox checks", result.stdout)

    def test_app_selection_and_installed_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            config_data = {"apps": [{"name": "first"}, {"name": "second"}]}
            write_config(config, config_data)
            result = self.run_main("--installed", config=config)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("apps:first second", result.stdout)
            result = self.run_main("--app second --installed --app first", config=config)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("apps:second first", result.stdout)
            self.assertEqual(self.run_main("--installed --app absent", config=config).returncode, 2)
            for code in (1, 2):
                with self.subTest(code=code):
                    result = self.run_main("--installed", config=config,
                                          overrides=f"installed_checks() {{ return {code}; }}")
                    self.assertEqual(result.returncode, code)

    def test_source_guards_do_not_run_host_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            script = "HOME=" + shlex.quote(directory) + "\n"
            script += "command() { echo 'unexpected command check' >&2; return 1; }\n"
            script += "ip() { echo 'unexpected ip' >&2; return 1; }\n"
            script += "systemctl() { echo 'unexpected systemctl' >&2; return 1; }\n"
            host_scripts = (
                *sorted((ROOT / "bin").iterdir()),
                *sorted((ROOT / "host").iterdir()),
                *sorted((ROOT / "lib").glob("*.sh")),
            )
            for path in host_scripts:
                script += f"source {shlex.quote(str(path))}\n"
            result = shell(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout + result.stderr, "")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_host_entrypoints_are_executable(self):
        for name in ("up", "down"):
            with self.subTest(name=name):
                self.assertTrue(os.access(ROOT / "host" / name, os.X_OK))

    def test_installed_checks_aggregate_failures_and_clean_fixtures(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "calls"
            fixture = Path(directory) / "fixture"
            fixture.mkdir()
            runtime = Path(directory) / "runtime.json"
            runtime.write_text("{}")
            script = f'''source {shlex.quote(str(RUNNER))}
PROXY_CONFIG={shlex.quote(str(runtime))}
require_commands() {{ return 0; }}
sudo() {{ echo 'nftables: filtered'; }}
mktemp() {{ echo {shlex.quote(str(fixture))}; }}
APPS=(first second)
verify_app() {{ echo "$1" >> {shlex.quote(str(marker))}; [[ $1 == second ]]; }}
installed_checks
'''
            # EUID cannot be overridden; this contract runs as a normal user.
            if os.geteuid() == 0:
                self.skipTest("installed mode requires a normal user")
            result = shell(script)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(marker.read_text().splitlines(), ["first", "second"])
            self.assertFalse(fixture.exists())

    def test_probes_are_delivered_without_repo_read_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            boundary = path / "tests/boundary"
            boundary.mkdir(parents=True)
            (boundary / "test_boundary.sh").write_text(
                '#!/bin/bash\nprintf "%s\\n" "$SANDBOX_TEST_PASSED" "$SANDBOX_TEST_ENDPOINTS"\n'
                '[[ -f "$(dirname "$0")/boundary_probe.py" ]]\n')
            (boundary / "boundary_probe.py").write_text("# transported fixture\n")
            config = path / "config.toml"
            runtime = path / "runtime.json"
            config_data = {
                "apps": [
                    {
                        "name": "demo",
                        "dir.write": [directory],
                        "endpoints": ["example.com"],
                    },
                ],
            }
            write_config(config, config_data)
            runtime_data = {"apps": [{"name": "demo", "endpoints": ["example.com"]}]}
            runtime.write_text(json.dumps(runtime_data))
            script = f'''source {shlex.quote(str(RUNNER))}
SANDBOX_ROOT={shlex.quote(directory)}
CONFIG={shlex.quote(str(config))}; PROXY_CONFIG={shlex.quote(str(runtime))}
FIXTURE={shlex.quote(str(path / "fixture"))}
sudo() {{
    shift 2
    while [[ $1 != bash ]]; do
        case $1 in
        --env) export "$2"; shift 2 ;;
        --app) shift 2 ;;
        *) return 2 ;;
        esac
    done
    "$@"
}}
verify_app demo
'''
            result = shell(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["two words=a=b", '["example.com"]'])

    def test_cleanup_removes_only_owned_fixtures_on_exit_and_interrupt(self):
        for ending, code in (("exit 0", 0), ("kill -TERM $$", 143)):
            with self.subTest(ending=ending), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                fixture = path / "fixture"
                fixture.mkdir()
                test_file, unrelated = path / "test-file", path / "unrelated"
                test_file.touch()
                unrelated.touch()
                script = f'''source {shlex.quote(str(RUNNER))}
FIXTURE={shlex.quote(str(fixture))}
TEST_FILES=({shlex.quote(str(test_file))})
trap cleanup EXIT
trap 'exit 143' TERM
{ending}
'''
                result = shell(script)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertFalse(fixture.exists())
                self.assertFalse(test_file.exists())
                self.assertTrue(unrelated.exists())


class BoundaryTests(unittest.TestCase):
    def test_shared_lock_reads_without_changing_file_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "settings.toml"
            settings.write_text('version = "12"\n')
            original = settings.read_bytes()
            probe.locked_read(settings)
            self.assertEqual(settings.read_bytes(), original)

    def test_config_probe_refuses_to_modify_a_writable_host_file(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "sandbox.toml"
            config.write_text("preserve config\n")
            with self.assertRaisesRegex(AssertionError, "mount is writable"):
                probe.readonly_config(config)
            self.assertEqual(config.read_text(), "preserve config\n")

    def test_positive_write_control_cleans_file(self):
        fixture_environment = {"SANDBOX_TEST_FIXTURE": "/var/tmp/example"}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, fixture_environment):
            probe.writable_directory(directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_write_failure_does_not_delete_an_existing_file(self):
        fixture_environment = {"SANDBOX_TEST_FIXTURE": "/var/tmp/example"}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, fixture_environment):
            file = Path(directory) / ".sandbox-test-example"
            file.write_text("preserve")
            with self.assertRaises(FileExistsError):
                probe.writable_directory(directory)
            self.assertEqual(file.read_text(), "preserve")

    def test_shared_directory_leak_is_reported_and_cleaned(self):
        fixture_environment = {"SANDBOX_TEST_FIXTURE": "/var/tmp/example"}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, fixture_environment):
            with self.assertRaisesRegex(AssertionError, "shared directory is writable"):
                probe.readonly_directory(directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_other_app_state_requires_permission_denial(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AssertionError, "state directory is accessible"):
                probe.private_directory(directory)
            with patch.object(probe.os, "scandir", side_effect=PermissionError):
                probe.private_directory(directory)

    def test_denied_tls_requires_handshake_rejection(self):
        with patch.object(probe.socket, "create_connection") as connect, \
                patch.object(probe.ssl, "_create_unverified_context") as context:
            connection = connect.return_value.__enter__.return_value
            context.return_value.wrap_socket.side_effect = probe.ssl.SSLError("rejected")
            probe.tls("host", "blocked.invalid", False)
            context.return_value.wrap_socket.assert_called_once_with(connection, server_hostname="blocked.invalid")
            context.return_value.wrap_socket.side_effect = None
            with self.assertRaises(AssertionError):
                probe.tls("host", "blocked.invalid", False)

    def test_offline_proxy_does_not_count_as_tls_denial(self):
        with patch.object(probe.socket, "create_connection", side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                probe.tls("host", "blocked.invalid", False)
