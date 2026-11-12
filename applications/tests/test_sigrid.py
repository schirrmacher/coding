import subprocess
import tempfile
import unittest
from pathlib import Path
from test_support import ROOT, load_module
setup = load_module("install_sigrid", ROOT.parent / "applications/sigrid/install.py")
class SigridInstallerTests(unittest.TestCase):
    def test_runtime_uses_installed_package_without_changing_host_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            package = home / ".local/share/sigrid/sigrid"
            package.mkdir(parents=True)
            (package / "__init__.py").touch()
            (package / "cli.py").write_text(
                'import sys\ndef main():\n    print("SIGRID test help", *sys.argv[1:])\n    return 0\n')
            original = home / ".local/bin/sigrid"
            original.parent.mkdir(parents=True)
            original.write_text("keep host launcher")
            launcher = setup.prepare_sigrid(home)
            self.assertEqual(setup.prepare_sigrid(home), launcher)
            result = subprocess.run([str(launcher), "--help"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "SIGRID test help --help\n")
            self.assertEqual(original.read_text(), "keep host launcher")

    def test_missing_installation_does_not_create_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "not installed"):
                setup.prepare_sigrid(directory)
            self.assertFalse((Path(directory) / ".local/share/sandbox").exists())
