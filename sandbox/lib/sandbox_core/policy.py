"""Effective identities and grants derived from normalized configuration."""
from dataclasses import dataclass
import re


def desktop_metadata(app, home):
    from .legacy import desktop_defaults
    return {**desktop_defaults(app["name"], home), **app.get("desktop", {})}


def desktop_enabled(app):
    return desktop_metadata(app, "").get("enabled", app.get("gui", False))


def desktop_ids(app):
    if app.get("launchers"):
        return tuple(app["launchers"])
    metadata = desktop_metadata(app, "")
    return (metadata.get("id", f'{app["name"]}-sandboxed.desktop'),)


def split_env_prefix(command):
    """Extract only simple leading env assignments; preserve complex invocations."""
    if not command or command[0].rsplit("/", 1)[-1] != "env":
        return {}, command
    environment = {}
    offset = 1
    while offset < len(command) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", command[offset]):
        key, value = command[offset].split("=", 1)
        environment[key] = value
        offset += 1
    if offset == len(command) or command[offset].startswith("-"):
        return {}, command
    return environment, command[offset:]


def command_executable(command):
    if not command:
        return None
    return split_env_prefix(command)[1][0]


def command_environment(app):
    assignments, _ = split_env_prefix(app.get("cmd", []))
    return {**app.get("env", {}), **assignments}


@dataclass(frozen=True)
class AppPolicy:
    name: str
    command: tuple[str, ...]
    environment: dict[str, str]
    writable: tuple[str, ...]
    readable: tuple[str, ...]
    private: tuple[str, ...]
    desktops: tuple[str, ...]
    offline: bool
    gui: bool
    sigrid: bool
    pty: bool

    @classmethod
    def from_config(cls, data, name):
        from .legacy import environment_defaults, pty_default
        app = next(app for app in data["apps"] if app["name"] == name)
        dirs = app.get("dir", {})
        writable = tuple(dict.fromkeys([*dirs.get("write", []),
                    *([app["codex_home"]] if app.get("codex_home") else []), *dirs.get("state", [])]))
        readable = tuple(dirs.get("read", []))
        granted = set(writable + readable)
        private = []
        for other in data["apps"]:
            if other["name"] == name:
                continue
            paths = [*([other["codex_home"]] if other.get("codex_home") else []),
                     *other.get("dir", {}).get("state", [])]
            private.extend(path for path in paths if path not in granted)
        return cls(name, tuple(app.get("cmd", [])), {**environment_defaults(name), **app.get("env", {})}, writable,
                   readable, tuple(dict.fromkeys(private)), desktop_ids(app), app.get("endpoints") == [], app.get("gui", False),
                   app.get("sigrid", False), app.get("pty", pty_default(name)))
