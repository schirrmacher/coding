"""State inventories create directories and preserve automatic app isolation."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from test_support import ROOT, load_module, native_config

loader = load_module("native_policy_loader", ROOT / "lib/read_definitions.py")
runtime = load_module("native_runtime", ROOT / "lib/create_app_state.py")
import sys
sys.path.insert(0, str(ROOT / "lib"))
from read_definitions import AppPolicy
sys.path.pop(0)


class StatePolicyTests(unittest.TestCase):
    def test_state_inventory_does_not_implicitly_grant_file_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "private"
            path = native_config(root / "sandbox.toml", {"owner": {"state": str(state)}, "other": {}})
            data = loader.read_config(path, root / "absent")
            self.assertEqual(AppPolicy.from_config(data, "owner").writable, ())
            self.assertEqual(AppPolicy.from_config(data, "other").private, (str(state),))
            runtime.create_app_state(data, root)
            self.assertTrue(state.is_dir())
            (state / "keep").write_text("existing")
            runtime.create_app_state(data, root)
            self.assertEqual((state / "keep").read_text(), "existing")

    def test_shared_inventory_and_exact_bind_exempt_intentional_sharing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = str(root / "shared")
            path = native_config(root / "sandbox.toml", {
                "first": {"state": state}, "second": {"state": state},
                "reader": {"mounts.args": f"--ro-bind\n{state}\n{state}\n"},
                "broad": {"mounts.args": f"--bind\n{root}\n{root}\n"}})
            data = loader.read_config(path, root / "absent")
            for name in ("first", "second", "reader"):
                self.assertEqual(AppPolicy.from_config(data, name).private, ())
            self.assertEqual(AppPolicy.from_config(data, "broad").private, (state,))

    def test_executable_preparation_hooks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root / "sandbox.toml", {"demo": {"prepare.sh": "exit 0"}})
            with self.assertRaisesRegex(ValueError, "unknown app file"):
                loader.read_config(path, root / "absent")

    def test_root_preparation_is_rejected_before_creating_state_or_running_scripts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            data = {"apps": [{"dir": {"state": [str(state)]}, "files": {"prepare.sh": "/unused"}}]}
            with patch.object(runtime.os, "geteuid", return_value=0):
                with self.assertRaisesRegex(ValueError, "unprivileged"):
                    runtime.create_app_state(data, root)
            self.assertFalse(state.exists())
