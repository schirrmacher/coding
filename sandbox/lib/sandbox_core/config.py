#!/usr/bin/env python3
"""Read and normalize the public and private TOML policy."""
import hashlib
import json
import os
import pwd
import re
import tomllib
from pathlib import Path


def read_config(path, local_path=None, home=None):
    with Path(path).open("rb") as file:
        data = tomllib.load(file)

    home = home if home is not None else user_home()
    apps = data.get("apps", [])
    if not isinstance(apps, list):
        raise ValueError("apps must be an array of tables")
    names = set()
    for app in apps:
        if not isinstance(app, dict) or not isinstance(app.get("name"), str) or not re.fullmatch(r"[a-z][a-z0-9-]*", app["name"]):
            raise ValueError("every app name must match [a-z][a-z0-9-]*")
        if app["name"] in names:
            raise ValueError("duplicate app names")
        names.add(app["name"])
        expand_app(app, home)
    local_path = Path(local_path) if local_path is not None else Path(home) / ".config/sandbox/local.toml"
    data["config_paths"] = [str(Path(path).resolve(strict=True))]
    if local_path.exists() or local_path.is_symlink():
        try:
            with local_path.open("rb") as file:
                local = tomllib.load(file)
            merge_apps(data, local, home)
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise ValueError(f"{local_path}: {error}") from error
        data["config_paths"].append(str(local_path.resolve(strict=True)))
    for app in data.get("apps", []):
        for mode, paths in app.get("dir", {}).items():
            app["dir"][mode] = list(dict.fromkeys(str(Path(item).resolve()) for item in paths))
        if isinstance(app.get("codex_home"), str):
            if not Path(app["codex_home"]).is_absolute():
                raise ValueError("codex_home must be an absolute directory path")
            app["codex_home"] = str(Path(app["codex_home"]).resolve())
        if "endpoints" in app:
            app["endpoints"] = list(dict.fromkeys(item.lower().rstrip(".") for item in app["endpoints"]))
    policy = json.dumps(data, sort_keys=True, allow_nan=False).encode()
    data["policy_fingerprint"] = hashlib.sha256(policy).hexdigest()
    return data


def expand_app(app, home):
    from .schema import validate_app_fields
    validate_app_fields(app)
    if "env" in app:
        app["env"] = {key: expand_home(value, home) for key, value in app["env"].items()}
    if "desktop" in app:
        app["desktop"] = {key: expand_home(value, home) for key, value in app["desktop"].items()}

    for legacy, replacement in (("directories", "dir.write"), ("readable_directories", "dir.read")):
        if legacy in app:
            raise ValueError(f"{legacy} is no longer supported; use {replacement}")
    directories = app.get("dir", {})
    if not isinstance(directories, dict) or directories.keys() - {"read", "write", "state"}:
        raise ValueError("dir must be a table containing only read, write, and state")
    for mode, paths in directories.items():
        invalid_paths = (not isinstance(paths, list) or (mode == "write" and not paths)
                         or any(not isinstance(path, str) or not path for path in paths))
        if invalid_paths:
            required_entries = " with at least one entry" if mode == "write" else ""
            raise ValueError(f"dir.{mode} must be an array of non-empty paths{required_entries}")
        expanded = expand_home(paths, home)
        if any(not Path(item).is_absolute() for item in expanded):
            raise ValueError(f"dir.{mode} must contain absolute paths")
        directories[mode] = expanded
    for key in ("cmd", "codex_home"):
        if key not in app:
            continue
        app[key] = expand_home(app[key], home)
    if "endpoints" in app:
        values = app["endpoints"]
        if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
            raise ValueError("endpoints must be an array of non-empty strings")


def merge_apps(data, local, home):
    if "directories" in local:
        raise ValueError("directories is no longer supported; use [[apps]] with dir.read/dir.write")
    if local.keys() - {"apps"}:
        raise ValueError("local config may contain only apps")
    entries = local.get("apps", [])
    if not isinstance(entries, list):
        raise ValueError("apps must be an array of tables")
    apps = {app["name"]: app for app in data.get("apps", [])}
    allowed = {"name", "dir", "endpoints", "cmd", "gui", "wrapper_name", "launchers", "codex_home", "sigrid", "env", "desktop", "pty"}
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.keys() - allowed:
            raise ValueError("local app entries accept only " + ", ".join(sorted(allowed)))
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("local app name must be a non-empty string")
        if name not in apps:
            raise ValueError(f"unknown app '{name}'")
        if name in seen:
            raise ValueError(f"duplicate local app '{name}'")
        seen.add(name)
        expand_app(entry, home)
        for mode, paths in entry.get("dir", {}).items():
            if mode == "state":
                continue
            for path in paths:
                if not Path(path).is_dir():
                    raise ValueError(f"directory '{path}' does not exist")
        app = apps[name]
        for key, value in entry.items():
            if key == "name":
                continue
            if key == "dir":
                for mode, paths in value.items():
                    app.setdefault("dir", {}).setdefault(mode, []).extend(paths)
            elif key == "endpoints":
                app.setdefault(key, []).extend(value)
            elif key in ("env", "desktop"):
                app.setdefault(key, {}).update(value)
            else:
                app[key] = value


def user_home():
    uid = int(os.environ.get("SUDO_UID", os.getuid()))
    return pwd.getpwuid(uid).pw_dir


def expand_home(value, home):
    if isinstance(value, list):
        return [expand_home(item, home) for item in value]
    if not isinstance(value, str):
        return value

    expanded = value.replace("${HOME}", home)
    if "${" in expanded:
        raise ValueError("only ${HOME} is supported in path and command settings")
    return expanded
