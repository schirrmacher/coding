"""Codex preparation preserves independent releases and original launchers."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_support import ROOT, load_module

codex_setup = load_module("prepare_codex", ROOT / "lib/prepare_codex.py")


def release(path, version="0.160.0"):
    path.mkdir()
    (path / "bin").mkdir()
    (path / "codex-resources").mkdir()
    (path / "codex-path").mkdir()
    (path / "codex-package.json").write_text(json.dumps({"version": version, "target": "test-linux"}))
    (path / "codex-resources/resource").write_text("resource contents")
    (path / "codex-path/rg").write_text("search helper")
    binary = path / "bin/codex"
    binary.write_text(f"#!/bin/sh\necho codex-cli {version}\n")
    binary.chmod(0o755)
    helper = path / "bin/codex-code-mode-host"
    helper.write_text("code mode helper")
    helper.chmod(0o755)
    (path / "codex").symlink_to("bin/codex")
    return path


class CodexPreparationTests(unittest.TestCase):
    def test_complete_release_is_independent_and_repeated_installs_keep_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = release(path / "source")
            destination = path / "independent"
            executable = codex_setup.prepare_codex(source, destination)
            self.assertEqual(executable, destination / "current/bin/codex")
            self.assertTrue(executable.resolve().is_relative_to(destination))
            installed = (destination / "current").resolve()
            self.assertEqual((installed / "codex").readlink(), Path("bin/codex"))
            self.assertEqual((installed / "codex-path/rg").read_text(), "search helper")
            self.assertEqual((installed / "bin/codex-code-mode-host").read_text(), "code mode helper")
            self.assertEqual((installed / "codex-resources/resource").read_text(), "resource contents")
            self.assertEqual(codex_setup.prepare_codex(source, destination), executable)
            shutil.rmtree(source)
            self.assertEqual(codex_setup.prepare_codex(source, destination), executable)
            self.assertEqual(subprocess.check_output([executable, "--version"], text=True).strip(),
                             "codex-cli 0.160.0")

    def test_modified_release_is_rejected_without_overwriting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = release(path / "source")
            destination = path / "independent"
            codex_setup.prepare_codex(source, destination)
            resource = destination / "current/codex-resources/resource"
            resource.write_text("modified contents")
            with self.assertRaisesRegex(ValueError, "conflicting.*contents"):
                codex_setup.prepare_codex(source, destination)
            self.assertEqual(resource.read_text(), "modified contents")

    def test_current_link_into_orca_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = release(path / "orca")
            destination = path / "independent"
            destination.mkdir()
            (destination / "current").symlink_to(source)
            with self.assertRaisesRegex(ValueError, "conflicting.*current"):
                codex_setup.prepare_codex(source, destination)

    def test_releases_directory_cannot_link_back_into_orca(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = release(path / "orca")
            destination = path / "independent"
            destination.mkdir()
            (destination / "releases").symlink_to(path)
            (destination / "current").symlink_to("releases/orca")
            with self.assertRaisesRegex(ValueError, "conflicting.*directory"):
                codex_setup.prepare_codex(source, destination)

    def test_external_release_links_are_rejected_before_copying(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = release(path / "source")
            outside = path / "outside"
            outside.write_text("host data")
            (source / "codex-resources/external").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "escapes"):
                codex_setup.prepare_codex(source, path / "independent")
            self.assertFalse((path / "independent").exists())

    def test_failed_copy_leaves_no_published_release_and_can_be_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = release(path / "source")
            destination = path / "independent"
            with patch.object(codex_setup.shutil, "copytree", side_effect=OSError("copy failed")):
                with self.assertRaisesRegex(OSError, "copy failed"):
                    codex_setup.prepare_codex(source, destination)
            self.assertEqual(list((destination / "releases").iterdir()), [])
            self.assertFalse((destination / "current").exists())
            self.assertTrue(codex_setup.prepare_codex(source, destination).is_file())

    def test_separate_updates_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = release(path / "source")
            update = release(path / "update", "0.161.0")
            destination = path / "independent"
            (destination / "releases").mkdir(parents=True)
            installed = destination / "releases/0.161.0-test-linux"
            shutil.copytree(update, installed, symlinks=True)
            (destination / "current").symlink_to("releases/0.161.0-test-linux")
            executable = codex_setup.prepare_codex(source, destination)
            self.assertEqual(executable.resolve(), installed / "bin/codex")

    def test_wrong_version_or_missing_helper_does_not_publish_a_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = release(path / "source")
            (source / "bin/codex").write_text("#!/bin/sh\necho codex-cli 0.1.0\n")
            with self.assertRaisesRegex(ValueError, "does not match"):
                codex_setup.prepare_codex(source, path / "independent")
            (source / "bin/codex-code-mode-host").unlink()
            with self.assertRaisesRegex(ValueError, "missing codex-code-mode-host"):
                codex_setup.prepare_codex(source, path / "independent")
            self.assertFalse((path / "independent").exists())
