"""Agent launchers share the sandbox GitHub state explicitly."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from test_support import ROOT, load_module, native_config

loader = load_module("gh_native_loader", ROOT / "lib/read_definitions.py")


class GithubStateTests(unittest.TestCase):
    def test_native_readonly_bind_does_not_grant_write_permissions_in_apparmor(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = native_config(Path(temporary) / "sandbox.toml", {"reader": {
                "apparmor": '"/shared/" r,\n"/shared/**" rmk,\ndeny "/shared/**" wl,\n',
                "mounts.args": "--ro-bind\n/shared\n/shared\n"}})
            app = loader.read_config(path, Path(temporary) / "absent")["apps"][0]
            self.assertEqual(app["dir"]["read"], ["/shared"])
            self.assertIn('deny "/shared/**" wl,', app["apparmor"])
