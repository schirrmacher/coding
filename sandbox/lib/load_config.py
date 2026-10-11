#!/usr/bin/env python3
"""Compatibility CLI for the shared configuration loader."""
import json
import os
import pwd
import sys
from sandbox_core.config import expand_app, expand_home, merge_apps, user_home
from sandbox_core.config import read_config as _read_config
from sandbox_core.policy import command_environment


def read_config(path, local_path=None):
    return _read_config(path, local_path, home=user_home())


if __name__ == "__main__":
    try:
        print(json.dumps(read_config(*sys.argv[1:]), allow_nan=False))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"cannot parse config {sys.argv[1]}: {error}", file=sys.stderr)
        sys.exit(1)
