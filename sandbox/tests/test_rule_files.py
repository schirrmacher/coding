"""Rule artifacts compose standalone policies and fail before host installation."""
import shutil
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_support import ROOT, load_module, run_bash, write_config

secrets = load_module("secret_rules", ROOT / "lib/render_secret_rules.py")


class RuleFileTests(unittest.TestCase):
    def test_secret_inventory_preserves_directory_and_file_distinction(self):
        with tempfile.TemporaryDirectory() as temporary:
            inventory = Path(temporary) / "secrets.toml"
            inventory.write_text('directories = [".ssh"]\nfiles = [".netrc"]\n')
            with patch.object(secrets, "INVENTORY", inventory):
                self.assertEqual(secrets.render("masks", "/home/test"), "/home/test/.ssh")
                self.assertEqual(secrets.render("apparmor").splitlines(), [
                    "  deny @{HOME}/.ssh/ r,", "  deny @{HOME}/.ssh/** rwklmx,",
                    "  deny @{HOME}/.netrc rwklmx,"])

    def test_invalid_inventory_fails_in_both_formats(self):
        with tempfile.TemporaryDirectory() as temporary:
            inventory = Path(temporary) / "secrets.toml"
            for content in ('invalid [', 'directories = []',
                            'directories = ["../secret"]\nfiles = []',
                            'directories = ".ssh"\nfiles = []'):
                inventory.write_text(content)
                with self.subTest(content=content), patch.object(secrets, "INVENTORY", inventory):
                    for mode in ("apparmor", "masks"):
                        with self.assertRaises(ValueError):
                            secrets.render(mode, "/home/test")

    def test_profile_is_standalone_and_renders_outside_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.toml"
            write_config(config, {"apps": [{"name": "demo", "gui": True, "pty": True,
                                          "browser": True, "sigrid": True}]})
            result = run_bash(f'''cd /tmp
source {shlex.quote(str(ROOT / 'host/up'))}
CONFIG={shlex.quote(str(config))}
render_apparmor demo /tmp
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("profile sandbox-demo ", result.stdout)
            for permission in ("userns,", "deny @{HOME}/.ssh/** rwklmx,", "OpenURI",
                               "org.freedesktop.secrets", "FileChooser", "/dev/ptmx rw,"):
                self.assertIn(permission, result.stdout)
            self.assertNotIn("@BASE_RULES@", result.stdout)
            self.assertNotIn("@DIRECTORY_RULES@", result.stdout)
            self.assertNotIn("#include <sandbox/", result.stdout)

    def test_missing_fragments_and_invalid_secrets_stop_profile_rendering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "rules", root / "rules")
            (root / "lib").mkdir()
            shutil.copy(ROOT / "lib/render_secret_rules.py", root / "lib/render_secret_rules.py")
            prefix = f'''source {shlex.quote(str(ROOT / 'lib/render_apparmor.sh'))}
APPARMOR_RULES={shlex.quote(str(root / 'rules/apparmor'))}
app_file_rules() {{ :; }}
app_sigrid_rules() {{ :; }}
app_browser_rules() {{ :; }}
app_gui_rules() {{ :; }}
app_pty_rules() {{ :; }}
'''
            for name in ("profile", "base"):
                fragment = root / "rules/apparmor" / name
                original = fragment.read_text()
                fragment.unlink()
                result = run_bash(prefix + "render_apparmor demo /tmp")
                self.assertNotEqual(result.returncode, 0, name)
                fragment.write_text(original)
            (root / "rules/secrets.toml").write_text("invalid [")
            result = run_bash(prefix + "render_apparmor demo /tmp")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot render secret rules", result.stderr)
            result = run_bash(f'''source {shlex.quote(str(ROOT / 'rules/bubblewrap.sh'))}
BUBBLEWRAP_RULES={shlex.quote(str(root / 'rules'))}
build_mask_args /tmp
''')
            self.assertNotEqual(result.returncode, 0)

    def test_missing_firewall_file_stops_before_nft_is_called(self):
        result = run_bash(f'''source {shlex.quote(str(ROOT / 'lib/host/configure_network.sh'))}
NETWORK_RULES=/nonexistent-sandbox-rules
POOL_CIDR=10.77.0.0/24; SNI_PORT=3128; DNS_PORT=53
nft() {{ echo 'unexpected nft call' >&2; }}
install_firewall
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("unexpected nft call", result.stderr)
