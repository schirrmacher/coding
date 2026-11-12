"""Local native files replace public files without field-specific merge rules."""
import tempfile
import unittest
from pathlib import Path
from test_support import ROOT, load_module, native_config

loader = load_module("native_local_loader", ROOT / "lib/read_definitions.py")


class LocalConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.public = native_config(self.root / "sandbox.toml", {"demo": {"endpoints": "public.example\n", "apparmor": "#include <sandbox/browser>\n"}})
        self.local = self.root / "local-apps"
        (self.local / "demo").mkdir(parents=True)

    def test_empty_local_file_removes_public_permissions(self):
        (self.local / "demo/apparmor").write_text("")
        data = loader.read_config(self.public, self.local)
        self.assertEqual(data["apps"][0]["apparmor"], "\n")
        self.assertEqual(data["apps"][0]["endpoints"], ["public.example"])

    def test_local_endpoints_replace_and_do_not_append(self):
        (self.local / "demo/endpoints").write_text("local.example\n")
        data = loader.read_config(self.public, self.local)
        self.assertEqual(data["apps"][0]["endpoints"], ["local.example"])
        (self.local / "demo/endpoints").write_text("")
        self.assertEqual(loader.read_config(self.public, self.local)["apps"][0]["endpoints"], [])

    def test_unknown_local_app_and_unknown_file_fail(self):
        (self.local / "unknown").mkdir()
        with self.assertRaisesRegex(ValueError, "unknown local apps"):
            loader.read_config(self.public, self.local)
        (self.local / "unknown").rmdir()
        (self.local / "demo/policy.toml").write_text("")
        with self.assertRaisesRegex(ValueError, "unknown app file"):
            loader.read_config(self.public, self.local)

    def test_every_effective_file_and_app_membership_affects_fingerprint(self):
        first = loader.read_config(self.public, self.local)
        override = self.local / "demo/endpoints"
        override.write_text("local.example\n")
        second = loader.read_config(self.public, self.local)
        self.assertNotEqual(first["policy_fingerprint"], second["policy_fingerprint"])
        override.unlink()
        self.assertEqual(first["policy_fingerprint"], loader.read_config(self.public, self.local)["policy_fingerprint"])
        native_config(self.public, {"extra": {}})
        self.assertNotEqual(first["policy_fingerprint"], loader.read_config(self.public, self.local)["policy_fingerprint"])

    def test_replaced_public_content_is_not_an_effective_source(self):
        (self.local / "demo/endpoints").write_text("local.example\n")
        before = loader.read_config(self.public, self.local)
        (self.root / "apps/demo/endpoints").write_text("unused.example\n")
        after = loader.read_config(self.public, self.local)
        self.assertEqual(before["policy_fingerprint"], after["policy_fingerprint"])
        self.assertIn(str(self.local / "demo/endpoints"), after["config_paths"])
        self.assertIn(str(self.local), after["config_directories"])

    def test_desktop_and_shell_scripts_use_the_same_replacement_rule(self):
        script = self.local / "demo/launch.sh"
        script.write_text('#!/bin/sh\nexec /bin/echo local "$@"\n')
        (self.local / "demo/demo.desktop").write_text('[Desktop Entry]\nName=Local\nExec=demo %F\n')
        data = loader.read_config(self.public, self.local)
        app = data["apps"][0]
        self.assertEqual(app["cmd"], ["/bin/sh", str(script)])
        self.assertIn("Name=Local", app["desktops"]["demo.desktop"])
