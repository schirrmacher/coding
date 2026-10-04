#!/usr/bin/env python3
"""Preserve the installed uv binary before replacing its command with a wrapper."""

import filecmp
import os
import shutil
import subprocess
import sys
from pathlib import Path

from load_config import user_home


def prepare_uv(home):
    home = Path(home)
    launcher = home / ".local/bin/uv"
    runtime = home / ".local/share/sandbox/runtimes/uv/uv"
    backup = home / ".local/share/sandbox/original-launchers/uv"
    marker = b'#!/usr/bin/env bash\n# sandbox-managed wrapper for app "uv"'

    if launcher.is_symlink():
        if not (launcher.resolve() == runtime.resolve() and runtime.is_file() and not runtime.is_symlink()):
            raise ValueError(f"refusing to replace unmanaged launcher: {launcher}")
        return
    if launcher.is_file():
        with launcher.open("rb") as file:
            managed = file.read(len(marker)) == marker
        if managed:
            if not runtime.is_file() or runtime.is_symlink() or not os.access(runtime, os.X_OK):
                raise ValueError(f"uv runtime missing or invalid: {runtime}")
            return
    elif not launcher.exists() and runtime.is_file() and not runtime.is_symlink():
        return

    with launcher.open("rb") as file:
        if file.read(4) != b"\x7fELF" or not os.access(launcher, os.X_OK):
            raise ValueError(f"refusing to replace unmanaged launcher: {launcher}")
    version = subprocess.run([str(launcher), "--version"], check=True, capture_output=True, text=True)
    if not version.stdout.startswith("uv "):
        raise ValueError(f"not a uv executable: {launcher}")

    for path, label in ((backup, "launcher backup"), (runtime, "uv runtime")):
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_symlink() or not path.is_file() or not filecmp.cmp(launcher, path, shallow=False):
            raise ValueError(f"conflicting {label}: {path}")

    # Validate both destinations before writing either; never overwrite a backup.
    for path in (backup, runtime):
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(launcher, path)


if __name__ == "__main__":
    try:
        prepare_uv(user_home())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"cannot prepare uv runtime: {error}", file=sys.stderr)
        sys.exit(1)
