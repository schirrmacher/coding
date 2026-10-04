#!/usr/bin/env python3
"""Bootstrap an independent Codex release without changing PATH wrappers or state."""

import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from load_config import user_home


def verify_release(root):
    root = Path(root).resolve(strict=True)
    metadata = json.loads((root / "codex-package.json").read_text())
    version, target = metadata["version"], metadata["target"]
    if any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", value)
           for value in (version, target)):
        raise ValueError("invalid Codex release version or target")
    for entry in root.rglob("*"):
        if entry.is_symlink() and not entry.resolve(strict=True).is_relative_to(root):
            raise ValueError(f"Codex release link escapes its installation: {entry}")
    for name in ("codex-resources", "codex-path"):
        if not (root / name).is_dir():
            raise ValueError(f"Codex release is missing {name}")
    helper = root / "bin/codex-code-mode-host"
    if not helper.is_file():
        raise ValueError("Codex release is missing codex-code-mode-host")
    if not os.access(helper, os.X_OK):
        raise ValueError("Codex code-mode helper is not executable")
    result = subprocess.run([str(root / "bin/codex"), "--version"],
                            text=True, capture_output=True, check=True, timeout=15)
    if result.stdout.strip() != f"codex-cli {version}":
        raise ValueError(f"Codex executable does not match release version {version}")
    return f"{version}-{target}"


def same_release(source, destination):
    source_entries = {entry.relative_to(source): entry for entry in source.rglob("*")}
    destination_entries = {entry.relative_to(destination): entry for entry in destination.rglob("*")}
    if source_entries.keys() != destination_entries.keys():
        return False
    for name, source_entry in source_entries.items():
        destination_entry = destination_entries[name]
        if source_entry.is_symlink() or destination_entry.is_symlink():
            if not (source_entry.is_symlink() and destination_entry.is_symlink()
                    and source_entry.readlink() == destination_entry.readlink()):
                return False
            continue

        if source_entry.is_dir() or destination_entry.is_dir():
            if not (source_entry.is_dir() and destination_entry.is_dir()):
                return False
            continue

        if not filecmp.cmp(source_entry, destination_entry, shallow=False):
            return False
    return True


def prepare_codex(source, destination):
    source, destination = Path(source), Path(destination)
    releases = destination / "releases"
    current = destination / "current"
    if destination.is_symlink() or releases.is_symlink():
        raise ValueError(f"conflicting Codex installation directory: {destination}")
    installed = None
    if current.exists() or current.is_symlink():
        if not current.is_symlink() or current.resolve().parent != releases.resolve():
            raise ValueError(f"conflicting Codex current path: {current}")
        installed = current.resolve(strict=True)
        verify_release(installed)
        if not source.exists():
            return current / "bin/codex"

    source = source.resolve(strict=True)
    release_name = verify_release(source)
    # Preserve a separately updated independent installation on wrapper regeneration.
    if installed is not None and installed.name != release_name:
        return current / "bin/codex"
    release = releases / release_name
    if release.exists() or release.is_symlink():
        if release.is_symlink() or not same_release(source, release):
            raise ValueError(f"conflicting Codex release contents: {release}")
        verify_release(release)
    else:
        releases.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".codex-release-", dir=releases) as temporary:
            staged = Path(temporary) / release_name
            shutil.copytree(source, staged, symlinks=True)
            verify_release(staged)
            staged.rename(release)

    if installed is None:
        with tempfile.TemporaryDirectory(prefix=".codex-current-", dir=destination) as temporary:
            link = Path(temporary) / "current"
            link.symlink_to(f"releases/{release_name}")
            link.replace(current)
    return current / "bin/codex"


def main():
    home = Path(user_home())
    source = home / ".config/orca/codex-runtime-home/home/packages/standalone/current"
    executable = prepare_codex(source, home / ".local/share/codex")
    print(f"Independent Codex runtime: {executable}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"cannot prepare Codex runtime: {error}", file=sys.stderr)
        sys.exit(1)
