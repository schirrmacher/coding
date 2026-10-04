"""Shared module loading and dependency-free TOML fixtures."""
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
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def run_bash(script):
    return subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + script], text=True, capture_output=True,
        env=isolated_environment(),
    )


def write_config(path, data):
    lines = []
    for key, value in data.items():
        if value is not None and not isinstance(value, dict) and key not in ("apps", "directories"):
            lines.append(f"{key} = {json.dumps(value)}")

    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        lines.append(f"[{key}]")
        lines.extend(
            f"{name} = {json.dumps(item)}"
            for name, item in value.items()
            if item is not None
        )

    for key in ("apps", "directories"):
        for app in data.get(key, []):
            lines.append(f"[[{key}]]")
            lines.extend(
                f"{name} = {json.dumps(item)}"
                for name, item in app.items()
                if item is not None and not isinstance(item, dict)
            )

            for name, table in app.items():
                if isinstance(table, dict):
                    lines.append(f"[{key}.{name}]")
                    lines.extend(f"{field} = {json.dumps(value)}" for field, value in table.items())

    path.write_text("\n".join(lines) + "\n")
