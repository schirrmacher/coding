"""Every installer has a harmless help command and no sandbox imports."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from test_support import ROOT, load_module

APPLICATIONS = ROOT.parent / 'applications'


class InstallerContracts(unittest.TestCase):
    def test_every_installer_documents_its_command_without_installing(self):
        for script in [*sorted(APPLICATIONS.glob('*/install.py')), APPLICATIONS / 'update.py']:
            with self.subTest(app=script.parent.name), tempfile.TemporaryDirectory() as temporary:
                result = subprocess.run([sys.executable, str(script), '--help'],
                                        env={**os.environ, 'HOME': temporary}, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)
                self.assertEqual(list(Path(temporary).iterdir()), [])
                tree = ast.parse(script.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        self.assertFalse((node.module or '').startswith(('sandbox', 'read_definitions')))

    def test_browser_initialization_preserves_preferences_on_repeated_install(self):
        brave = load_module('install_brave', APPLICATIONS / 'brave/install.py')
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            brave.install(home)
            settings = home / '.local/share/sandbox/brave/Default/Preferences'
            original = settings.read_text()
            brave.install(home)
            self.assertEqual(settings.read_text(), original)
            self.assertIn(str(home / 'Downloads'), original)
            settings.write_text('{"download":{"default_directory":"/custom"},"other":42}')
            brave.install(home)
            self.assertEqual(settings.read_text(), '{"download":{"default_directory":"/custom"},"other":42}')
