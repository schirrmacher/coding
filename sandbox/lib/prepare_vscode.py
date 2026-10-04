#!/usr/bin/env python3
"""Seed separate VS Code settings and extensions without copying running sessions."""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from load_config import read_config, user_home


def prepare_vscode(user_data, extensions, home):
    user_data = Path(user_data)
    extensions = Path(extensions)
    home = Path(home)
    original_user_data = home / ".config/Code"
    original_extensions = home / ".vscode/extensions"
    if user_data.resolve() == original_user_data.resolve():
        raise ValueError("sandbox user data must be separate from the host profile")
    if extensions.resolve() == original_extensions.resolve():
        raise ValueError("sandbox extensions must be separate from the host extensions")

    if not user_data.exists():
        user_data.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".vscode-profile-", dir=user_data.parent) as temporary:
            staged_profile = Path(temporary) / "user-data"
            user_directory = staged_profile / "User"
            user_directory.mkdir(parents=True)
            for name in ("settings.json", "keybindings.json", "snippets", "profiles"):
                source = original_user_data / "User" / name
                destination = user_directory / name
                if source.is_dir():
                    shutil.copytree(source, destination)
                elif source.is_file():
                    shutil.copy2(source, destination)
            staged_profile.rename(user_data)

    original_arguments = home / ".vscode/argv.json"
    isolated_arguments = user_data.parent / "argv.json"
    if original_arguments.is_file() and not isolated_arguments.exists():
        shutil.copy2(original_arguments, isolated_arguments)

    if extensions.exists():
        return
    extensions.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".vscode-extensions-", dir=extensions.parent) as temporary:
        staged_extensions = Path(temporary) / "extensions"
        if original_extensions.is_dir():
            shutil.copytree(original_extensions, staged_extensions)
        else:
            staged_extensions.mkdir()
        staged_extensions.rename(extensions)


def main():
    config_path = Path(__file__).resolve().parents[1] / "sandbox.toml"
    app = next(app for app in read_config(config_path)["apps"] if app["name"] == "vscode")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-data-dir", required=True)
    parser.add_argument("--extensions-dir", required=True)
    args, _ = parser.parse_known_args(app["cmd"][1:])
    prepare_vscode(args.user_data_dir, args.extensions_dir, user_home())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"cannot prepare VS Code profile: {error}", file=sys.stderr)
        sys.exit(1)
