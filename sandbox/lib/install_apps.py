#!/usr/bin/env python3
"""Install pinned apps and direct agent links; sandbox policy stays in TOML."""

import argparse
import filecmp
import gzip
import hashlib
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from load_config import read_config, user_home

ASSETS = {
    "zed-linux-x86_64.tar.gz": (
        "https://github.com/zed-industries/zed/releases/download/v1.23.2/zed-linux-x86_64.tar.gz",
        "cabddd5af2b26a19633ea39f5dde070e2aad204bb815bfa74cb65073ffd5ff39",
    ),
    "bwrap-linux-x86_64.gz": (
        "https://github.com/zed-industries/zed/releases/download/v1.23.2/bwrap-linux-x86_64.gz",
        "f385d58fb4ba9d4fd55afff8b528bcb42f430a6f914c3013250f28f6ee213f3f",
    ),
    "herdr-linux-x86_64": (
        "https://github.com/herdrdev/herdr/releases/download/v0.9.3/herdr-linux-x86_64",
        "18a8dc65f1c2fa485884344356dea1cfd911c6f06cf46fa78e193f4087f4dba7",
    ),
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
    zed = home / ".local/zed.app"
    herdr = home / ".local/share/herdr/bin/herdr"
    for executable, version in ((zed / "bin/zed", "Zed 1.23.2 "), (herdr, "herdr 0.9.3")):
        if executable.exists():
            result = subprocess.run([str(executable), "--version"], check=True,
                                    capture_output=True, text=True, timeout=15)
            if not result.stdout.strip().startswith(version):
                raise ValueError(f"different version already installed: {executable}")
    if not zed.exists():
        zed.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".zed-install-", dir=zed.parent) as temporary:
            with tarfile.open(directory / "zed-linux-x86_64.tar.gz") as archive:
                archive.extractall(temporary, filter="data")
            (Path(temporary) / "zed.app").rename(zed)
    if not (zed / "bin/zed").is_file():
        raise ValueError(f"incomplete Zed installation: {zed}")
    helper = zed / "bin/bwrap"
    with gzip.open(directory / "bwrap-linux-x86_64.gz", "rb") as source:
        contents = source.read()
    if helper.exists() and helper.read_bytes() != contents:
        raise ValueError(f"conflicting Zed bubblewrap helper: {helper}")
    helper.write_bytes(contents)
    helper.chmod(0o755)
    if not herdr.exists():
        herdr.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(directory / "herdr-linux-x86_64", herdr)
        herdr.chmod(0o755)
    for executable in (zed / "bin/zed", helper, herdr):
        result = subprocess.run([str(executable), "--version"], check=True,
                                capture_output=True, text=True, timeout=15)
        print(result.stdout.strip())
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


def install_agent_links(home, apps):
    home = Path(home)
    state = home / ".local/share/sandbox/herdr"
    bin_dir = state / "bin"
    for name in ("bin", "config/herdr", "data", "cache", "state", "codex", "claude", "gh", "cargo", "uv"):
        (state / name).mkdir(parents=True, exist_ok=True)
    for app in apps:
        if app["name"] not in ("claude", "codex", "opencode", "gh", "cargo", "uv", "herdr"):
            continue
        from sandbox_core.policy import command_executable
        executable = command_executable(app.get("cmd", []))
        if not executable or not Path(executable).is_file():
            continue
        target = Path(executable)
        link = bin_dir / app["name"]
        if link.is_symlink() and link.readlink() == target:
            continue
        if link.exists() or link.is_symlink():
            raise ValueError(f"conflicting Herdr runtime link: {link}")
        link.symlink_to(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-dir", type=Path,
                        help="reuse release downloads after verifying their checksums")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("these releases require Linux x86_64")
    home = Path(user_home())
    root = Path(__file__).resolve().parents[1]
    directory = args.download_dir or home / ".cache/sandbox/app-downloads"
    fetch_assets(directory)
    install_binaries(home, directory)
    install_agent_links(home, read_config(root / "sandbox.toml")["apps"])


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"cannot install apps: {error}", file=sys.stderr)
        sys.exit(1)
