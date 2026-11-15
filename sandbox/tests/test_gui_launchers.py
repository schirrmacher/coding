"""Native desktop entries retain actions, URI arguments and official identities."""
import shlex
import tempfile
import unittest
from pathlib import Path
from test_support import ROOT, load_module, native_config, run_bash

desktop = load_module("native_desktop", ROOT / "src/render_desktop.py")


class LauncherTests(unittest.TestCase):
    def test_native_gui_include_contains_display_gpu_fonts_and_filechooser_permissions(self):
        loader = load_module("gui_loader", ROOT / "src/read_definitions.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root, {"gui": {"apparmor": "#include <sandbox/gui>\n"}, "cli": {}})
            apps = {app["name"]: app for app in loader.read_config(path, root / "absent")["apps"]}
            text = apps["gui"]["apparmor"]
            for permission in ("<abstractions/X>", "<abstractions/fonts>", "/sys/devices/pci*/{,**}",
                               "FileChooser", "member={OpenFile,SaveFile,SaveFiles}", "member=Response"):
                self.assertIn(permission, text)
            self.assertNotIn("OpenURI", text)
            self.assertNotIn("FileChooser", apps["cli"]["apparmor"])

    def test_actions_metadata_and_original_desktop_backups_survive_regeneration(self):
        with tempfile.TemporaryDirectory(prefix="native desktop ") as temporary:
            root = Path(temporary)
            entry = ('[Desktop Entry]\nName=Visual Studio Code\nIcon=vscode\nStartupWMClass=Code\n'
                     'Exec="/path with spaces/code" %F\nMimeType=text/plain;\n'
                     '[Desktop Action new]\nName=New Window\nExec=code --new-window %F\n')
            config = native_config(root, {"vscode": {
                "launch.sh": '#!/bin/sh\nexec /usr/bin/code "$@"\n', "wrappers": "code\n",
                "com.microsoft.VSCode.desktop": entry,
                "com.microsoft.VSCode.UrlHandler.desktop": '[Desktop Entry]\nNoDisplay=true\nMimeType=x-scheme-handler/vscode;\nExec=code --open-url %U\n'}})
            installed = root / "installed"
            installed.mkdir()
            original = installed / "com.microsoft.VSCode.desktop"
            original.write_text("[Desktop Entry]\nName=Personal Code\nExec=code %F\n")
            snapshot = original.read_text()
            for _ in range(2):
                result = run_bash(f'''source {shlex.quote(str(ROOT / 'install'))}
CONFIG={shlex.quote(str(config))}; DESKTOP_DIR={shlex.quote(str(installed))}
DESKTOP_BACKUP_DIR={shlex.quote(str(root / 'backups'))}; BIN_DIR={shlex.quote(str(root / 'bin'))}
write_desktop_entry vscode
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((root / "backups/com.microsoft.VSCode.desktop").read_text(), snapshot)
                main = original.read_text()
                self.assertIn('Exec="' + str(root / 'bin/code') + '" --new-window %F', main)
                self.assertIn("StartupWMClass=Code", main)
                self.assertIn("MimeType=text/plain;", main)
                urls = (installed / "com.microsoft.VSCode.UrlHandler.desktop").read_text()
                self.assertIn('Exec="' + str(root / 'bin/code') + '" --open-url %U', urls)
                self.assertIn("NoDisplay=true", urls)

    def test_conflicting_desktop_backup_is_rejected_before_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "demo.desktop"
            path.write_text("original")
            backups = root / "backups"
            backups.mkdir()
            (backups / path.name).write_text("conflict")
            result = run_bash(f'''source {shlex.quote(str(ROOT / 'install'))}
DESKTOP_BACKUP_DIR={shlex.quote(str(backups))}
preserve_desktop_entry {shlex.quote(str(path))}
''')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_text(), "original")

    def test_renderer_preserves_terminal_prefix_and_native_arguments(self):
        source = ('[Desktop Entry]\nName=Herdr (sandboxed)\n'
                  'Exec=/usr/bin/gnome-terminal --app-id=dev.herdr.Herdr --window -- app %F\n')
        rendered = desktop.render_native_desktop(source, '"/managed/herdr" ', "/managed/herdr")
        self.assertIn('Exec=/usr/bin/gnome-terminal --app-id=dev.herdr.Herdr --window -- "/managed/herdr" %F', rendered)
        self.assertNotIn("(sandboxed)", rendered)
        self.assertIn("TryExec=/managed/herdr", rendered)

    def test_renderer_preserves_quoted_arguments_and_rejects_missing_exec(self):
        source = '[Desktop Entry]\nExec="/path with spaces/code" --goto "two words.py:10" %F\n'
        self.assertIn('Exec="sandbox" --goto "two words.py:10" %F', desktop.render_desktop_entry(source, '"sandbox" '))
        with self.assertRaisesRegex(ValueError, "no Exec"):
            desktop.render_desktop_entry("[Desktop Entry]\nName=Code\n", '"sandbox" ')
