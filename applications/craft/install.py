#!/usr/bin/env python3
"""Install checksum-pinned Craft releases independently of sandbox setup."""

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

ASSETS = {
    "photocraft-0.21.0-linux-x86_64.AppImage": (
        "https://github.com/storytold/photocraft/releases/download/v0.21.0/photocraft-0.21.0-linux-x86_64.AppImage",
        "7726533adaa5896413d2ce0be858d522256450bfef244fbc5433bed4f99fa60b",
    ),
    "vectorcraft-0.22.0-linux-x86_64.AppImage": (
        "https://github.com/storytold/vectorcraft/releases/download/v0.22.0/vectorcraft-0.22.0-linux-x86_64.AppImage",
        "09a68d22232530219c12643bb7e9eda6b1f6778cbf9f2f2fc46ff96e2259f7b0",
    ),
    "designcraft-0.18.0-linux-x86_64.AppImage": (
        "https://github.com/storytold/designcraft/releases/download/v0.18.0/designcraft-0.18.0-linux-x86_64.AppImage",
        "013640920f00af2a4fca09c1bcd44d97bd404f68e1bd8665377335f2c12c20d3",
    ),
    "wordcraft-0.16.0-linux-x86_64.AppImage": (
        "https://github.com/storytold/wordcraft/releases/download/v0.16.0/wordcraft-0.16.0-linux-x86_64.AppImage",
        "980ac1d6918f1c1e0c240d859374f22b19e524d3af3372daef1344c5a097ae17",
    ),
    "deckcraft-0.16.0-linux-x86_64.AppImage": (
        "https://github.com/storytold/deckcraft/releases/download/v0.16.0/deckcraft-0.16.0-linux-x86_64.AppImage",
        "1211d8b517377eed0fc037d64daef1b75b7ee278e0620ab0d7e7beb6e86183f7",
    ),
    "gridcraft-0.17.0-linux-x86_64.AppImage": (
        "https://github.com/storytold/gridcraft/releases/download/v0.17.0/gridcraft-0.17.0-linux-x86_64.AppImage",
        "0455c863535822d951a1a91fdee8dd029369e0f2f93f7ac99c4916ef70a87761",
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
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or not filecmp.cmp(source, destination, shallow=False):
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=f".{app}-",
                                             delete=False) as temporary:
                staged = Path(temporary.name)
            try:
                shutil.copy2(source, staged)
                staged.chmod(0o755)
                staged.replace(destination)
            finally:
                staged.unlink(missing_ok=True)
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
    home = Path(Path.home())
    directory = args.download_dir or home / ".cache/sandbox/app-downloads"
    fetch_assets(directory)
    install_binaries(home, directory)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"cannot install apps: {error}", file=sys.stderr)
        sys.exit(1)
