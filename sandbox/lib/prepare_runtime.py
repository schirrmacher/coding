#!/usr/bin/env python3
"""Prepare configured runtimes as the invoking user, preserving existing state."""
import json
import shutil
import sys
from pathlib import Path
from load_config import user_home
from sandbox_core.policy import command_executable, desktop_metadata
from prepare_codex import prepare_codex
from prepare_uv import prepare_uv
from prepare_vscode import prepare_vscode
from prepare_sigrid import prepare_sigrid
from prepare_zed import prepare_zed


def prepare_runtime(data, home):
    home = Path(home)
    assets = Path(__file__).resolve().parents[1] / "assets"
    for app in data["apps"]:
        presentation = desktop_metadata(app, str(home))
        terminal_app_id = presentation.get("terminal_app_id")
        if terminal_app_id:
            server = next((path for path in (Path("/usr/libexec/gnome-terminal-server"),
                                             Path("/usr/lib/gnome-terminal/gnome-terminal-server"))
                           if path.is_file()), None)
            if server is None:
                raise ValueError("a dedicated terminal launcher requires GNOME Terminal")
            service = home / ".local/share/dbus-1/services" / f"{terminal_app_id}.service"
            service.parent.mkdir(parents=True, exist_ok=True)
            service.write_text(f"[D-BUS Service]\nName={terminal_app_id}\n"
                               f"Exec={server} --app-id={terminal_app_id}\n")
        icon = presentation.get("icon", "")
        if icon and Path(icon).name == icon and (assets / f"{icon}.svg").is_file():
            destination = home / ".local/share/icons/hicolor/scalable/apps" / f"{icon}.svg"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(assets / f"{icon}.svg", destination)
        for directory in app.get("dir", {}).get("state", []):
            Path(directory).mkdir(parents=True, exist_ok=True)
    if any(app.get("sigrid", False) for app in data["apps"]):
        prepare_sigrid(home)
    executables = {command_executable(app.get("cmd", [])) for app in data["apps"]}
    if str(home / ".local/zed.app/bin/zed") in executables:
        prepare_zed(home, home / ".local/zed.app")
    if str(home / ".local/share/sandbox/runtimes/uv/uv") in executables:
        prepare_uv(home)
    if str(home / ".local/share/codex/current/bin/codex") in executables:
        prepare_codex(home / ".config/orca/codex-runtime-home/home/packages/standalone/current",
                      home / ".local/share/codex")
    for app in data["apps"]:
        if command_executable(app.get("cmd", [])) == "/usr/bin/code":
            command = app["cmd"]
            if "--user-data-dir" in command and "--extensions-dir" in command:
                prepare_vscode(command[command.index("--user-data-dir") + 1],
                               command[command.index("--extensions-dir") + 1], home)


if __name__ == "__main__":
    try:
        prepare_runtime(json.load(sys.stdin), sys.argv[1] if len(sys.argv) > 1 else user_home())
    except (OSError, ValueError) as error:
        print(f"cannot prepare runtimes: {error}", file=sys.stderr)
        sys.exit(1)
