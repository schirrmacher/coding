"""SIGRID runtime and desktop bus access stay confined to opted-in apps."""
import shlex
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_support import ROOT, load_module, run_bash, write_config

loader = load_module("sigrid_config", ROOT / "lib/read_definitions.py")


class SigridTests(unittest.TestCase):
    def test_native_include_grants_only_secret_service_permissions(self):
        from test_support import native_config
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root / "sandbox.toml", {"enabled": {"apparmor": "#include <sandbox/secret-service>\n"}, "disabled": {}})
            apps = {app["name"]: app for app in loader.read_config(path, root / "absent")["apps"]}
            self.assertIn("org.freedesktop.secrets", apps["enabled"]["apparmor"])
            self.assertIn("owner /run/user/*/bus rw", apps["enabled"]["apparmor"])
            self.assertNotIn("org.freedesktop.secrets", apps["disabled"]["apparmor"])

    def test_bus_mount_is_declared_explicitly_without_exposing_the_runtime_directory(self):
        from test_support import native_config
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root / "sandbox.toml", {"agent": {"mounts.args": "--ro-bind\n/run/user/${UID}/bus\n/run/user/${UID}/bus\n"}})
            app = loader.read_config(path, root / "absent")["apps"][0]
            self.assertEqual(app["mounts"][0], "--ro-bind")
            self.assertTrue(app["mounts"][1].endswith("/bus"))
            self.assertEqual(app["mounts"][1], app["mounts"][2])
