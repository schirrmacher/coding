"""Native browser portal permissions and the HTTP-only runtime opener."""
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from test_support import ROOT, load_module, native_config

loader = load_module("browser_native_loader", ROOT / "lib/read_definitions.py")


class BrowserTests(unittest.TestCase):
    def test_portal_permission_requires_an_explicit_native_include(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root / "sandbox.toml", {"enabled": {"apparmor": "#include <sandbox/browser>\n"}, "disabled": {}})
            apps = {app["name"]: app for app in loader.read_config(path, root / "absent")["apps"]}
            self.assertIn("OpenURI", apps["enabled"]["apparmor"])
            self.assertNotIn("FileChooser", apps["enabled"]["apparmor"])
            self.assertNotIn("org.freedesktop.secrets", apps["enabled"]["apparmor"])
            self.assertNotIn("OpenURI", apps["disabled"]["apparmor"])

    def test_shared_opener_rejects_files_and_missing_urls(self):
        for arguments in ([], ["file:///etc/passwd"], ["--help"], ["https://example.com", "extra"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run([str(ROOT / "bin/open_browser"), *arguments], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("HTTP_URL", result.stderr)
