"""Zed setup keeps user settings while disabling both telemetry channels."""
import json
import tempfile
import unittest
from pathlib import Path
from test_support import ROOT, load_module

zed = load_module("prepare_zed", ROOT / "lib/prepare_zed.py")


class ZedPreparationTests(unittest.TestCase):
    def test_telemetry_update_preserves_jsonc_and_unrelated_values(self):
        source = '''{
  // Keep this comment and these preferences.
  "theme": "comma,} and https://example.test",
  "telemetry": {"diagnostics": true, "metrics": true, "other": 1,},
  "editor": {"font_size": 14},
}
'''
        rendered = zed.disable_telemetry(source)
        self.assertIn('// Keep this comment and these preferences.', rendered)
        self.assertIn('"theme": "comma,} and https://example.test"', rendered)
        self.assertIn('"editor": {"font_size": 14}', rendered)
        self.assertIn('"diagnostics": false', rendered)
        self.assertIn('"metrics": false', rendered)
        self.assertIn('"other": 1', rendered)
        self.assertEqual(zed.disable_telemetry(rendered), rendered)

    def test_setup_installs_named_icon_and_keeps_original_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            installation = home / ".local/zed.app"
            icon = installation / "share/icons/hicolor/512x512/apps/zed.png"
            icon.parent.mkdir(parents=True)
            icon.write_bytes(b"official icon")
            settings = home / ".config/zed/settings.json"
            settings.parent.mkdir(parents=True)
            original = '{"theme": "user theme"}\n'
            settings.write_text(original)
            for _ in range(2):
                zed.prepare_zed(home, installation)
                self.assertEqual(json.loads(settings.read_text().replace(',}', '}'))["telemetry"],
                                 {"diagnostics": False, "metrics": False})
                self.assertEqual(settings.with_name("settings.json.pre-sandbox").read_text(), original)
                self.assertEqual((home / ".local/share/icons/hicolor/512x512/apps/dev.zed.Zed.png").read_bytes(), b"official icon")

    def test_invalid_settings_are_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            installation = home / "zed"
            icon = installation / "share/icons/hicolor/512x512/apps/zed.png"
            icon.parent.mkdir(parents=True)
            icon.write_bytes(b"icon")
            settings = home / ".config/zed/settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text('{ invalid settings')
            with self.assertRaises(ValueError):
                zed.prepare_zed(home, installation)
            self.assertEqual(settings.read_text(), '{ invalid settings')
            self.assertFalse(settings.with_name("settings.json.pre-sandbox").exists())
