"""Shared module loading and native app fixtures."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def isolated_environment():
    return {**os.environ, "LOCAL_CONFIG": str(ROOT / "tests/absent_local.toml")}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def run_bash(script):
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", "set -euo pipefail\n" + script], text=True, capture_output=True,
        env=isolated_environment(),
    )


def write_config(path, data):
    """Small native fixtures for command, mount and feature contracts."""
    import shlex
    apps = {}
    for app in data["apps"]:
        files = {"endpoints": "\n".join(app.get("endpoints", []))}
        mounts = []
        for mode, option in (("write", "--bind"), ("read", "--ro-bind")):
            for directory in app.get("dir", {}).get(mode, app.get("dir." + mode, [])):
                mounts.extend((option, directory, directory))
        files["mounts.args"] = "\n".join(mounts)
        files["apparmor"] = "\n".join(
            f"#include <sandbox/{fragment}>" for key, fragment in
            (("gui", "gui"), ("pty", "pty"), ("browser", "browser"), ("sigrid", "secret-service"))
            if app.get(key))
        if "cmd" in app:
            command = shlex.join(app["cmd"])
            files["launch.sh"] = ('#!/bin/sh\nif [ "${1-}" = --sandbox-command ]; then\n'
                                  'shift\nelse\nset -- ' + command + ' "$@"\nfi\nexec "$@"\n')
        apps[app["name"]] = files
    native_config(path, apps)


def native_config(path, apps):
    """Write native app files directly for loader and launcher contract tests."""
    path = Path(path)
    root = path / "apps"
    root.mkdir(parents=True, exist_ok=True)
    for name, files in apps.items():
        directory = root / name
        directory.mkdir(exist_ok=True)
        for filename, text in {"apparmor": "", "mounts.args": "", "endpoints": "", **files}.items():
            (directory / filename).write_text(text)
    return path
