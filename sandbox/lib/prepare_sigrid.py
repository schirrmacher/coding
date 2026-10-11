#!/usr/bin/env python3
"""Expose the installed SIGRID package without adding managed wrappers to PATH."""
import sys
from pathlib import Path

from load_config import user_home


def prepare_sigrid(home):
    home = Path(home)
    package = home / ".local/share/sigrid"
    if not (package / "sigrid/cli.py").is_file():
        raise ValueError("SIGRID is not installed; run make install in the SIGRID project first")
    directory = home / ".local/share/sandbox/runtimes/sigrid"
    directory.mkdir(parents=True, exist_ok=True)
    launcher = directory / "sigrid"
    launcher.write_text(
        f"#!{sys.executable}\nimport sys\nsys.path.insert(0, {str(package)!r})\n"
        "from sigrid.cli import main\nraise SystemExit(main())\n"
    )
    launcher.chmod(0o755)
    return launcher


if __name__ == "__main__":
    try:
        print(f"SIGRID runtime: {prepare_sigrid(user_home())}")
    except (OSError, ValueError) as error:
        print(f"cannot prepare SIGRID: {error}", file=sys.stderr)
        sys.exit(1)
