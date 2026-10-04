"""VS Code launchers preserve normal entry points while entering the sandbox."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from test_support import isolated_environment, ROOT, load_module, write_config

desktop = load_module("sandbox_desktop", ROOT / "lib/render_desktop.py")


def shell(script, directory):
    return subprocess.run(
        ["bash", "-c", script, "test", str(ROOT), str(directory)],
        text=True,
        capture_output=True,
        env=isolated_environment(),
    )


class LauncherTests(unittest.TestCase):
    def test_display_and_font_rules_are_only_granted_to_gui_apps(self):
        with tempfile.TemporaryDirectory() as directory:
            config_data = {"apps": [{"name": "vscode", "gui": True}, {"name": "cli"}]}
            write_config(Path(directory) / "config.toml", config_data)
            script = '''
source "$1/lib/query_config.sh"
source "$1/lib/render_apparmor.sh"
CONFIG="$2/config.toml"
app_gui_rules "$3"
'''
            for app, gui in (("vscode", True), ("cli", False)):
                with self.subTest(app=app):
                    result = subprocess.run(
                        ["bash", "-c", script, "test", str(ROOT), directory, app],
                        text=True, capture_output=True,
                        env=isolated_environment(),
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if gui:
                        self.assertIn("<abstractions/X>", result.stdout)
                        self.assertIn("<abstractions/fonts>", result.stdout)
                        self.assertIn("/newroot/tmp/.X11-unix/ rw", result.stdout)
                    else:
                        self.assertEqual(result.stdout, "")

    def test_code_wrapper_keeps_vscode_identity_and_forwards_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            config_data = {
                "apps": [{"name": "vscode", "wrapper_name": "code", "cmd": ["/usr/bin/code", "--wait"]}],
            }
            write_config(path / "config.toml", config_data)
            sudo = path / "sudo"
            sudo.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n')
            sudo.chmod(0o755)
            script = '''
source "$1/bin/sandbox_wrappers"
CONFIG="$2/config.toml"
BIN_DIR=$2
write_wrapper vscode
export PATH="$2:$PATH"
"$2/code" --goto 'two words.py:10'
'''
            result = shell(script, directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = ["-n", str(ROOT / "bin/sandbox"), "--app", "vscode", "/usr/bin/code", "--wait",
                        "--goto", "two words.py:10"]
            self.assertEqual(result.stdout.splitlines()[1:], expected)
            self.assertFalse((path / "vscode").exists())

    def test_desktop_overrides_preserve_window_actions_uri_arguments_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            system, installed = path / "system", path / "installed"
            system.mkdir()
            installed.mkdir()
            main = (
                "[Desktop Entry]\nName=Visual Studio Code\nIcon=vscode\n"
                "StartupWMClass=com.microsoft.VSCode\nExec=/usr/share/code/code %F\n"
                "[Desktop Action new-empty-window]\nName=New Empty Window\n"
                "Exec=/usr/share/code/code --new-window %F\n"
            )
            urls = (
                "[Desktop Entry]\nNoDisplay=true\nMimeType=x-scheme-handler/vscode;\n"
                "Exec=/usr/share/code/code --open-url %U\n"
            )
            (system / "com.microsoft.VSCode.desktop").write_text(main)
            (system / "com.microsoft.VSCode.UrlHandler.desktop").write_text(urls)
            config_data = {
                "apps": [{
                    "name": "vscode",
                    "cmd": ["/usr/bin/code", "--wait", "--user-data-dir", "/separate profile"],
                    "launchers": ["com.microsoft.VSCode.desktop", "com.microsoft.VSCode.UrlHandler.desktop"],
                }],
            }
            write_config(path / "config.toml", config_data)
            script = '''
source "$1/bin/sandbox_wrappers"
CONFIG="$2/config.toml"
SYSTEM_DESKTOP_DIR="$2/system"
DESKTOP_DIR="$2/installed"
DESKTOP_BACKUP_DIR="$2/backups"
write_desktop_entry vscode
write_desktop_entry vscode
'''
            result = shell(script, directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            generated_main = (installed / "com.microsoft.VSCode.desktop").read_text()
            generated_urls = (installed / "com.microsoft.VSCode.UrlHandler.desktop").read_text()
            self.assertIn("StartupWMClass=com.microsoft.VSCode", generated_main)
            self.assertIn("MimeType=x-scheme-handler/vscode;", generated_urls)
            self.assertIn("NoDisplay=true", generated_urls)
            commands = [line for line in (generated_main + generated_urls).splitlines() if line.startswith("Exec=")]
            self.assertEqual(len(commands), 3)
            for command in commands:
                self.assertTrue(command.startswith('Exec="sudo" "-n" '), command)
                self.assertIn('"--app" "vscode"', command)
                self.assertIn('"--user-data-dir" "/separate profile"', command)
            self.assertTrue(commands[0].endswith("%F"))
            self.assertTrue(commands[1].endswith("--new-window %F"))
            self.assertTrue(commands[2].endswith("--open-url %U"))
            self.assertEqual((system / "com.microsoft.VSCode.desktop").read_text(), main)

    def test_desktop_backup_survives_regeneration_and_conflicts_are_rejected(self):
        for conflicting_backup in (False, True):
            with self.subTest(conflict=conflicting_backup), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                (path / "system").mkdir()
                (path / "installed").mkdir()
                (path / "backups").mkdir()
                desktop_file = "com.microsoft.VSCode.desktop"
                (path / "system" / desktop_file).write_text("[Desktop Entry]\nExec=/usr/bin/code %F\n")
                original = "[Desktop Entry]\nName=My editor\nExec=/usr/bin/code %F\n"
                installed = path / "installed" / desktop_file
                installed.write_text(original)
                if conflicting_backup:
                    (path / "backups" / desktop_file).write_text("unrelated backup")
                write_config(path / "config.toml", {"apps": [{"name": "vscode", "cmd": ["/usr/bin/code"]}]})
                script = '''
source "$1/bin/sandbox_wrappers"
CONFIG="$2/config.toml"
SYSTEM_DESKTOP_DIR="$2/system"
DESKTOP_DIR="$2/installed"
DESKTOP_BACKUP_DIR="$2/backups"
write_desktop_override vscode com.microsoft.VSCode.desktop
write_desktop_override vscode com.microsoft.VSCode.desktop
'''
                result = shell(script, directory)
                if conflicting_backup:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(installed.read_text(), original)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual((path / "backups" / desktop_file).read_text(), original)

    def test_stale_cleanup_retains_active_wrapper_and_desktop_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for name in ("code", "vscode", "com.microsoft.VSCode.desktop", "vscode-sandboxed.desktop"):
                (path / name).write_text("# sandbox-managed\n")
            (path / "personal.desktop").write_text("[Desktop Entry]\nName=Personal\n")
            script = '''
source "$1/bin/sandbox_wrappers"
MANAGED_FILES=(code com.microsoft.VSCode.desktop)
remove_stale "$2" '.desktop'
remove_stale "$2" ''
'''
            result = shell(script, directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(sorted(file.name for file in path.iterdir()),
                             ["code", "com.microsoft.VSCode.desktop", "personal.desktop"])

    def test_launcher_metadata_rejects_directory_paths_and_name_collisions(self):
        invalid_apps = (
            [{"name": "vscode", "cmd": ["/usr/bin/code"], "wrapper_name": "../code"}],
            [{"name": "vscode", "cmd": ["/usr/bin/code"], "launchers": ["../code.desktop"]}],
            [{"name": "first", "cmd": ["tool"], "wrapper_name": "code"},
             {"name": "code", "cmd": ["tool"]}],
            [{"name": "first", "cmd": ["tool"], "gui": True, "launchers": ["code.desktop"]},
             {"name": "second", "cmd": ["tool"], "gui": True, "launchers": ["code.desktop"]}],
        )
        with tempfile.TemporaryDirectory() as directory:
            for apps in invalid_apps:
                with self.subTest(apps=apps):
                    write_config(Path(directory) / "config.toml", {"apps": apps})
                    script = '''
source "$1/lib/query_config.sh"
source "$1/lib/render_apparmor.sh"
CONFIG="$2/config.toml"
validate_launcher_config
'''
                    result = shell(script, directory)
                    self.assertNotEqual(result.returncode, 0)

    def test_desktop_renderer_preserves_quoted_executable_arguments(self):
        source = '[Desktop Entry]\nExec="/path with spaces/code" --goto "two words.py:10" %F\n'
        rendered = desktop.render_desktop_entry(source, '"sandbox" ')
        self.assertIn('Exec="sandbox" --goto "two words.py:10" %F', rendered)
        with self.assertRaisesRegex(ValueError, "no Exec"):
            desktop.render_desktop_entry("[Desktop Entry]\nName=Code\n", '"sandbox" ')
