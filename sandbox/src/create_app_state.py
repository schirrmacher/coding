#!/usr/bin/env python3
"""Create declared state directories without installing or configuring applications."""
import json
import os
import sys
from pathlib import Path


def create_app_state(data, home):
    if os.geteuid() == 0:
        raise ValueError("run runtime preparation as an unprivileged user")
    for app in data["apps"]:
        for directory in app["dir"].get("state", []):
            Path(directory).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    try:
        create_app_state(json.load(sys.stdin), sys.argv[1] if len(sys.argv) > 1 else str(Path.home()))
    except (OSError, ValueError) as error:
        print(f"cannot create app state: {error}", file=sys.stderr)
        sys.exit(1)
