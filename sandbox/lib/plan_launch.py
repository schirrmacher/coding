#!/usr/bin/env python3
"""Serialize a launch plan without evaluating shell text.

The shell supplies the context and argument groups with explicit lengths.
"""
import json
import sys
from sandbox_core.launch import LaunchContext


def main(arguments):
    context = LaunchContext(*arguments[:11])
    remaining = arguments[11:]
    groups = {}
    while remaining:
        name, count = remaining[:2]
        length = int(count)
        if length < 0 or len(remaining) < length + 2 or name in groups:
            raise ValueError("invalid launch argument group")
        groups[name] = remaining[2:2 + length]
        remaining = remaining[2 + length:]
    return context.command(groups)


if __name__ == "__main__":
    try:
        print(json.dumps(main(sys.argv[1:])))
    except (ValueError, KeyError, TypeError) as error:
        print(f"cannot plan launch: {error}", file=sys.stderr)
        sys.exit(1)
