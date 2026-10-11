"""Render desktop templates while retaining their actions and file arguments."""
import shlex

def render_desktop_entry(source, command_prefix, metadata=None):
    lines = []
    launch_count = 0
    section = ""
    remaining = dict(metadata or {})
    for line in source.splitlines():
        if line.startswith("["):
            if section == "[Desktop Entry]":
                lines.extend(f"{key}={value}" for key, value in remaining.items())
                remaining.clear()
            section = line
        key = line.partition("=")[0]
        if section == "[Desktop Entry]" and key in remaining:
            line = f"{key}={remaining.pop(key)}"
        if key == "Name" or key.startswith("Name["):
            line = line.removesuffix(" (sandboxed)")
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

    if section == "[Desktop Entry]":
        lines.extend(f"{key}={value}" for key, value in remaining.items())
    if not launch_count:
        raise ValueError("desktop entry has no Exec commands")
    return "\n".join(lines) + "\n"
