#!/usr/bin/env python3
"""Render the shipped secret inventory for AppArmor or Bubblewrap."""
import sys
import tomllib
from pathlib import Path, PurePosixPath

INVENTORY = Path(__file__).resolve().parents[1] / "rules/secrets.toml"


def render(mode, home=None):
    with INVENTORY.open("rb") as stream:
        data = tomllib.load(stream)
    if set(data) != {"directories", "files"}:
        raise ValueError("secret inventory requires directories and files")
    for paths in data.values():
        if not isinstance(paths, list):
            raise ValueError("secret paths must be lists")
        for path in paths:
            if (not isinstance(path, str) or not path or PurePosixPath(path).is_absolute()
                    or any(part in (".", "..", "") for part in path.split("/"))
                    or any(character in path for character in '\n\r\x00"\\*?[]{}@')):
                raise ValueError("secret paths must be literal home-relative paths")
    if mode == "masks":
        if home is None:
            raise ValueError("mask rendering requires a home directory")
        return "\n".join(str(Path(home) / path) for path in data["directories"])
    if mode != "apparmor":
        raise ValueError("unknown secret rule format")
    lines = []
    for path in data["directories"]:
        lines.extend((f'  deny @{{HOME}}/{path}/ r,', f'  deny @{{HOME}}/{path}/** rwklmx,'))
    lines.extend(f'  deny @{{HOME}}/{path} rwklmx,' for path in data["files"])
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        print(render(*sys.argv[1:]))
    except (OSError, ValueError, TypeError) as error:
        print(f"cannot render secret rules: {error}", file=sys.stderr)
        sys.exit(1)
