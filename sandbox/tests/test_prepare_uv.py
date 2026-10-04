"""uv preparation preserves binaries, backups, and separate updates."""
import shlex
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_support import ROOT, load_module, run_bash, write_config

uv_setup = load_module("prepare_uv", ROOT / "lib/prepare_uv.py")


class UvPreparationTests(unittest.TestCase):
    def installed_binary(self, home):
        launcher = home / ".local/bin/uv"
        launcher.parent.mkdir(parents=True)
        launcher.write_bytes(b"\x7fELF test uv binary")
        launcher.chmod(0o755)
        return launcher

    def prepare(self, home):
        with patch.object(uv_setup.subprocess, "run", return_value=SimpleNamespace(stdout="uv 0.9.0\n")):
            uv_setup.prepare_uv(home)

    def test_regular_uv_binary_is_backed_up_and_wrapper_regeneration_keeps_updated_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            launcher = self.installed_binary(home)
            original = launcher.read_bytes()
            self.prepare(home)
            self.prepare(home)
            executable = home / ".local/share/sandbox/runtimes/uv/uv"
            backup = home / ".local/share/sandbox/original-launchers/uv"
            self.assertEqual(executable.read_bytes(), original)
            self.assertEqual(backup.read_bytes(), original)
            config = home / "config.toml"
            write_config(config, {"apps": [{"name": "uv", "cmd": ["/usr/bin/env", str(executable)]}]})
            script = f'''source {shlex.quote(str(ROOT / "bin/sandbox_wrappers"))}
HOME={shlex.quote(directory)}; CONFIG={shlex.quote(str(config))}
BIN_DIR="$HOME/.local/bin"; BACKUP_DIR="$HOME/.local/share/sandbox/original-launchers"
write_wrapper uv
'''
            result = run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("sandbox-managed wrapper", launcher.read_text())
            executable.write_bytes(original + b"updated runtime")
            self.prepare(home)
            result = run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(executable.read_bytes(), original + b"updated runtime")
            self.assertEqual(backup.read_bytes(), original)

    def test_conflicting_backup_or_runtime_is_rejected_before_any_copy(self):
        for relative in ("original-launchers/uv", "runtimes/uv/uv"):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                launcher = self.installed_binary(home)
                original = launcher.read_bytes()
                conflict = home / ".local/share/sandbox" / relative
                conflict.parent.mkdir(parents=True)
                conflict.write_bytes(b"keep conflict")
                with self.assertRaisesRegex(ValueError, "conflicting"):
                    self.prepare(home)
                self.assertEqual(conflict.read_bytes(), b"keep conflict")
                self.assertEqual(launcher.read_bytes(), original)
                other = home / ".local/share/sandbox" / (
                    "runtimes/uv/uv" if relative == "original-launchers/uv" else "original-launchers/uv")
                self.assertFalse(other.exists())

    def test_unmanaged_scripts_links_and_other_binaries_are_not_replaced(self):
        for kind in ("script", "symlink", "other binary"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                launcher = self.installed_binary(home)
                if kind == "script":
                    launcher.write_text("#!/bin/bash\necho unrelated\n")
                elif kind == "symlink":
                    launcher.unlink()
                    target = home / "other-binary"
                    target.write_bytes(b"\x7fELF other binary")
                    launcher.symlink_to(target)
                with patch.object(uv_setup.subprocess, "run", return_value=SimpleNamespace(stdout="echo 1.0\n")):
                    with self.assertRaises(ValueError):
                        uv_setup.prepare_uv(home)
                self.assertFalse((home / ".local/share/sandbox/original-launchers/uv").exists())

    def test_managed_wrapper_with_missing_runtime_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            launcher = self.installed_binary(home)
            launcher.write_text('#!/usr/bin/env bash\n# sandbox-managed wrapper for app "uv"\n')
            with self.assertRaisesRegex(ValueError, "runtime missing"):
                uv_setup.prepare_uv(home)
