"""Render desktop templates while retaining their actions and file arguments."""
import shlex
import json
import sys
from pathlib import Path

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


def render_native_desktop(source, prefix, executable):
    lines = []
    for line in source.splitlines():
        if line.startswith("Exec=") and "gnome-terminal" in line.partition("=")[2].split(" -- ")[0] and " -- " in line:
            terminal, command = line.removeprefix("Exec=").split(" -- ", 1)
            rendered = render_desktop_entry("[Desktop Entry]\nExec=" + command, terminal + " -- " + prefix)
            line = next(item for item in rendered.splitlines() if item.startswith("Exec="))
        elif line.startswith("Exec="):
            rendered = render_desktop_entry("[Desktop Entry]\n" + line, prefix)
            line = next(item for item in rendered.splitlines() if item.startswith("Exec="))
        lines.append(line)
    return _native_metadata(lines, executable)


def _native_metadata(lines, executable):
    # Exec was already rewritten; metadata insertion must not rewrite it a second time.
    output = []
    section = ""
    for line in lines:
        if line.startswith("["):
            if section == "[Desktop Entry]":
                output.append("TryExec=" + executable)
            section = line
        if line.startswith("TryExec="):
            continue
        if line.startswith("Name=") or line.startswith("Name["):
            line = line.removesuffix(" (sandboxed)")
        output.append(line)
    if section == "[Desktop Entry]":
        output.append("TryExec=" + executable)
    if not any(line.startswith("Exec=") for line in output):
        raise ValueError("desktop entry has no Exec commands")
    return "\n".join(output) + "\n"



if __name__ == "__main__":
    try:
        if sys.argv[1] == "--native":

            data = json.load(sys.stdin)
            app = next(app for app in data["apps"] if app["name"] == sys.argv[2])
            print(render_native_desktop(app["desktops"][sys.argv[3]], sys.argv[4], sys.argv[5]), end="")
        else:
            source = Path(sys.argv[1]).read_text()
            metadata = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
            print(render_desktop_entry(source, sys.argv[2], metadata), end="")
    except (OSError, ValueError) as error:
        print(f"cannot generate desktop entry: {error}", file=sys.stderr)
        sys.exit(1)
