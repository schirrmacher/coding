#!/usr/bin/env python3
"""Route every desktop launch action through the configured sandbox command."""

import shlex
import sys
from pathlib import Path


def render_desktop_entry(source, command_prefix):
    lines = []
    launch_count = 0
    for line in source.splitlines():
        if not line.startswith("Exec="):
            lines.append(line)
            continue

        command = line.removeprefix("Exec=")
        lexer = shlex.shlex(command, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        if not lexer.get_token():
            raise ValueError("desktop Exec has no executable")
        arguments = command[lexer.instream.tell():].lstrip()
        lines.append("Exec=" + command_prefix + arguments)
        launch_count += 1

    if not launch_count:
        raise ValueError("desktop entry has no Exec commands")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    try:
        source = Path(sys.argv[1]).read_text()
        print(render_desktop_entry(source, sys.argv[2]), end="")
    except (OSError, ValueError) as error:
        print(f"cannot generate desktop entry: {error}", file=sys.stderr)
        sys.exit(1)
