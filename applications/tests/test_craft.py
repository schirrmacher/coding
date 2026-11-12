import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from test_support import ROOT, load_module
installer = load_module("install_craft", ROOT.parent / "applications/craft/install.py")
class CraftInstallerTests(unittest.TestCase):
    def test_corrupt_download_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in installer.ASSETS:
                (Path(directory) / name).write_bytes(b"corrupt download")
            with patch.object(installer.urllib.request, "urlopen") as download:
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    installer.fetch_assets(directory)
            download.assert_not_called()

    def test_installation_upgrades_apps_is_repeatable_and_preserves_config_and_agent_state(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            assets = home / "downloads"
            assets.mkdir()
            for name in installer.ASSETS:
                (assets / name).write_bytes(b"fixture")
            applications = home / "Applications"
            applications.mkdir()
            for app in ("photocraft", "vectorcraft", "designcraft", "wordcraft", "deckcraft", "gridcraft"):
                (applications / f"{app}-linux.AppImage").write_bytes(b"older release")
            config = home / "sandbox.toml"
            config.write_text("preserve config")
            def version(command, **kwargs):
                if "--appimage-extract" in command:
                    icon = Path(kwargs["cwd"]) / "squashfs-root" / command[-1]
                    icon.parent.mkdir()
                    icon.write_bytes(b"icon")
                return subprocess.CompletedProcess(command, 0, "")

            with patch.object(installer.subprocess, "run", side_effect=version), patch("builtins.print"):
                installer.install_binaries(home, assets)
                installer.install_binaries(home, assets)
            for name in ("photocraft", "vectorcraft", "designcraft", "wordcraft", "deckcraft", "gridcraft"):
                self.assertEqual((home / "Applications" / f"{name}-linux.AppImage").read_bytes(), b"fixture")
                self.assertEqual((home / ".local/share/icons/hicolor/256x256/apps" /
                                  f"ai.storyteller.{name}.png").read_bytes(), b"icon")
            self.assertEqual(config.read_text(), "preserve config")
