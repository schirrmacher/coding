#!/usr/bin/env python3
"""Install pinned desktop apps; sandbox policy stays in TOML."""

import argparse
import filecmp
import hashlib
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from load_config import user_home

ASSETS = {
    "photocraft-0.12.0-linux-x86_64.AppImage": (
        "https://github.com/storytold/photocraft/releases/download/v0.12.0/photocraft-0.12.0-linux-x86_64.AppImage",
        "da821339afce93b72991c7900a28f589eb06a885e0ab59ea702ddec9a280ac66",
    ),
    "vectorcraft-0.14.0-linux-x86_64.AppImage": (
        "https://github.com/storytold/vectorcraft/releases/download/v0.14.0/vectorcraft-0.14.0-linux-x86_64.AppImage",
        "89757a1e806164b95eae2cef9bdf98bf1a03ef10a9b2cc8a50bd05c54b74c792",
    ),
    "designcraft-0.11.0-linux-x86_64.AppImage": (
        "https://github.com/storytold/designcraft/releases/download/v0.11.0/designcraft-0.11.0-linux-x86_64.AppImage",
        "7e246a6f793719c9818e9d1497efec5e22308c91e42ff3b1fe5f3667ae3a6b8c",
    ),
}


def fetch_assets(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in ASSETS.items():
        destination = directory / name
        if not destination.exists():
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as file:
                shutil.copyfileobj(response, file)
            temporary.replace(destination)
        with destination.open("rb") as file:
            digest = hashlib.file_digest(file, "sha256").hexdigest()
        if digest != expected:
            raise ValueError(f"release checksum mismatch: {destination}")


def install_binaries(home, directory):
    home, directory = Path(home), Path(directory)
    for name in ASSETS:
        if not name.endswith(".AppImage"):
            continue
        app = name.split("-", 1)[0]
        destination = home / "Applications" / f"{app}-linux.AppImage"
        source = directory / name
        if destination.exists() and not filecmp.cmp(source, destination, shallow=False):
            raise ValueError(f"different app already installed: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
        destination.chmod(0o755)
        icon_name = f"ai.storyteller.{app}.png"
        with tempfile.TemporaryDirectory(prefix=f"{app}-icon-") as temporary:
            subprocess.run([str(destination), "--appimage-extract", icon_name],
                           cwd=temporary, check=True, timeout=30)
            icon = home / ".local/share/icons/hicolor/256x256/apps" / icon_name
            icon.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(temporary) / "squashfs-root" / icon_name, icon)
        print(f"Installed {app}: {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-dir", type=Path,
                        help="reuse release downloads after verifying their checksums")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("these releases require Linux x86_64")
    home = Path(user_home())
    directory = args.download_dir or home / ".cache/sandbox/app-downloads"
    fetch_assets(directory)
    install_binaries(home, directory)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"cannot install apps: {error}", file=sys.stderr)
        sys.exit(1)
