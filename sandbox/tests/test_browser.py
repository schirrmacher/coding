"""Browser access opens HTTP URLs through the host portal for opted-in apps."""
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_support import ROOT, load_module, run_bash, write_config

loader = load_module("browser_config", ROOT / "lib/load_config.py")
runtime = load_module("browser_runtime", ROOT / "lib/prepare_runtime.py")


class BrowserTests(unittest.TestCase):
    def test_portal_permission_requires_browser_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            write_config(config, {"apps": [{"name": "enabled", "browser": True},
                                           {"name": "disabled", "sigrid": True}]})
            for name in ("enabled", "disabled"):
                result = run_bash(f'''source {shlex.quote(str(ROOT / "lib/query_config.sh"))}
source {shlex.quote(str(ROOT / "lib/render_apparmor.sh"))}
CONFIG={shlex.quote(str(config))}
app_browser_rules {name}
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                if name == "enabled":
                    self.assertIn("org.freedesktop.portal.OpenURI member=OpenURI", result.stdout)
                    self.assertNotIn("FileChooser", result.stdout)
                    self.assertNotIn("org.freedesktop.secrets", result.stdout)
                else:
                    self.assertEqual(result.stdout, "")

    def test_local_override_can_disable_browser_and_rejects_non_boolean(self):
        with tempfile.TemporaryDirectory() as directory:
            public, local = Path(directory) / "public.toml", Path(directory) / "local.toml"
            write_config(public, {"apps": [{"name": "agent", "browser": True}]})
            write_config(local, {"apps": [{"name": "agent", "browser": False}]})
            self.assertFalse(loader.read_config(public, local)["apps"][0]["browser"])
            write_config(local, {"apps": [{"name": "agent", "browser": "true"}]})
            with self.assertRaisesRegex(ValueError, "browser must be true or false"):
                loader.read_config(public, local)

    def test_installed_opener_rejects_files_and_missing_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            runtime.prepare_runtime({"apps": [{"name": "agent", "browser": True}]}, home)
            opener = home / ".local/share/sandbox/runtimes/browser/xdg-open"
            for arguments in ([], ["file:///etc/passwd"], ["--help"],
                              ["https://example.com", "extra"]):
                with self.subTest(arguments=arguments):
                    result = subprocess.run([str(opener), *arguments], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("HTTP_URL", result.stderr)
