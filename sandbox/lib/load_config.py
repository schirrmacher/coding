#!/usr/bin/env python3
"""Convert the user TOML config to JSON for the shell's jq queries."""
import hashlib
import json
import os
import pwd
import sys
import tomllib
from pathlib import Path


def read_config(path, local_path=None):
    with Path(path).open("rb") as file:
        data = tomllib.load(file)

    home = user_home()
    for app in data.get("apps", []):
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
    local_path = Path(local_path) if local_path is not None else Path(home) / ".config/sandbox/local.toml"
    data["config_paths"] = [str(Path(path).resolve(strict=True))]
    if local_path.exists() or local_path.is_symlink():
        try:
            with local_path.open("rb") as file:
                local = tomllib.load(file)
            merge_directories(data, local, home)
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


def merge_directories(data, local, home):
    if local.keys() - {"directories"}:
        raise ValueError("local config may contain only directories")
    entries = local.get("directories", [])
    if not isinstance(entries, list):
        raise ValueError("directories must be an array of tables")
    apps = {app["name"]: app for app in data.get("apps", [])}
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.keys() - {"path", "apps", "read", "endpoints"}:
            raise ValueError("directory entries accept only path, apps, read, and endpoints")
        path = expand_home(entry.get("path"), home)
        if not isinstance(path, str) or not Path(path).is_absolute():
            raise ValueError("directory path must be absolute")
        path = Path(path).resolve(strict=True)
        if not path.is_dir():
            raise ValueError(f"directory '{path}' does not exist")
        if path in seen:
            raise ValueError(f"duplicate directory '{path}'")
        seen.add(path)
        for key in ("apps", "read", "endpoints"):
            values = entry.get(key, [])
            if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
                raise ValueError(f"{key} must be an array of non-empty strings")
            if key != "endpoints" and (set(values) - apps.keys()):
                raise ValueError(f"{key} names unknown apps: {sorted(set(values) - apps.keys())}")
        if set(entry.get("apps", [])) & set(entry.get("read", [])):
            raise ValueError("an app cannot have both apps and read access to the same directory")
        if not entry.get("apps") and not entry.get("read"):
            raise ValueError("directory needs at least one app in apps or read")
        for key, mode in (("apps", "write"), ("read", "read")):
            for name in dict.fromkeys(entry.get(key, [])):
                app = apps[name]
                app.setdefault("dir", {}).setdefault(mode, []).append(str(path))
                app.setdefault("endpoints", []).extend(entry.get("endpoints", []))


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


if __name__ == "__main__":
    try:
        print(json.dumps(read_config(*sys.argv[1:]), allow_nan=False))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"cannot parse config {sys.argv[1]}: {error}", file=sys.stderr)
        sys.exit(1)
