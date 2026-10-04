"""VS Code preparation copies settings once and excludes running sessions."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_support import ROOT, load_module

config_reader = load_module("sandbox_vscode_config", ROOT / "lib/load_config.py")
with patch.dict(sys.modules, {"load_config": config_reader}):
    vscode_setup = load_module("prepare_vscode", ROOT / "lib/prepare_vscode.py")


class VscodePreparationTests(unittest.TestCase):
    def test_failed_seed_leaves_no_partial_profile_and_can_be_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            original_user = home / ".config/Code/User"
            original_user.mkdir(parents=True)
            (original_user / "settings.json").write_text("settings")
            user_data, extensions = home / "isolated/user-data", home / "isolated/extensions"
            with patch.object(vscode_setup.shutil, "copy2", side_effect=OSError("copy failed")):
                with self.assertRaisesRegex(OSError, "copy failed"):
                    vscode_setup.prepare_vscode(user_data, extensions, home)
            self.assertFalse(user_data.exists())
            self.assertEqual(list(user_data.parent.iterdir()), [])
            vscode_setup.prepare_vscode(user_data, extensions, home)
            self.assertEqual((user_data / "User/settings.json").read_text(), "settings")

    def test_profile_is_seeded_once_without_sessions_and_remains_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            original_user = home / ".config/Code/User"
            original_user.mkdir(parents=True)
            settings = original_user / "settings.json"
            settings.write_text('{"editor.fontSize": 15}')
            (original_user / "workspaceStorage").mkdir()
            (home / ".config/Code/SingletonLock").write_text("running host session")
            original_extensions = home / ".vscode/extensions"
            original_extensions.mkdir(parents=True)
            (original_extensions / "extension.txt").write_text("installed extension")
            original_arguments = home / ".vscode/argv.json"
            original_arguments.write_text('{"disable-hardware-acceleration": true}')
            sandbox_state = home / ".local/share/sandbox/vscode"
            user_data = sandbox_state / "user-data"
            extensions = sandbox_state / "extensions"

            vscode_setup.prepare_vscode(user_data, extensions, home)
            self.assertEqual((user_data / "User/settings.json").read_text(), settings.read_text())
            self.assertEqual((extensions / "extension.txt").read_text(), "installed extension")
            self.assertEqual((sandbox_state / "argv.json").read_text(), original_arguments.read_text())
            self.assertFalse((user_data / "SingletonLock").exists())
            self.assertFalse((user_data / "User/workspaceStorage").exists())

            (user_data / "User/settings.json").write_text("sandbox settings")
            (extensions / "extension.txt").write_text("sandbox extension")
            (sandbox_state / "argv.json").write_text("sandbox arguments")
            vscode_setup.prepare_vscode(user_data, extensions, home)
            self.assertEqual((user_data / "User/settings.json").read_text(), "sandbox settings")
            self.assertEqual((extensions / "extension.txt").read_text(), "sandbox extension")
            self.assertEqual((sandbox_state / "argv.json").read_text(), "sandbox arguments")
            self.assertEqual(settings.read_text(), '{"editor.fontSize": 15}')
            self.assertEqual((original_extensions / "extension.txt").read_text(), "installed extension")

    def test_empty_host_profile_is_supported_and_shared_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            user_data, extensions = home / "isolated/user-data", home / "isolated/extensions"
            vscode_setup.prepare_vscode(user_data, extensions, home)
            self.assertTrue((user_data / "User").is_dir())
            self.assertTrue(extensions.is_dir())
            with self.assertRaisesRegex(ValueError, "separate"):
                vscode_setup.prepare_vscode(home / ".config/Code", extensions, home)
            with self.assertRaisesRegex(ValueError, "separate"):
                vscode_setup.prepare_vscode(user_data, home / ".vscode/extensions", home)
