#!/usr/bin/env python3
"""Expose validated policy operations to the source-only Bash adapters."""
import json
import sys
from sandbox_core.policy import AppPolicy, desktop_enabled, desktop_ids, desktop_metadata, command_executable
from sandbox_core.config import user_home
from sandbox_core.schema import validate_config, validate_launchers


def main():
    operation, *args = sys.argv[1:]
    data = json.load(sys.stdin)
    if operation == "validate":
        validate_config(data)
    elif operation == "validate-launchers":
        validate_launchers(data)
    elif operation == "desktops":
        for app in data["apps"]:
            if (args and app["name"] == args[0]) or (not args and "cmd" in app and desktop_enabled(app)):
                print("\n".join(desktop_ids(app)))
    elif operation == "desktop-apps":
        for app in data["apps"]:
            if "cmd" in app and desktop_enabled(app):
                print(app["name"])
    elif operation == "desktop-metadata":
        app = next(app for app in data["apps"] if app["name"] == args[0])
        print(json.dumps(desktop_metadata(app, args[1] if len(args) > 1 else user_home())))
    elif operation == "executable":
        app = next(app for app in data["apps"] if app["name"] == args[0])
        print(command_executable(app.get("cmd", [])) or "")
    elif operation == "environment":
        policy = AppPolicy.from_config(data, args[0])
        for key, value in policy.environment.items():
            sys.stdout.write(key + "\0" + value + "\0")
    else:
        policy = AppPolicy.from_config(data, args[0])
        value = getattr(policy, operation)
        print(json.dumps(value) if isinstance(value, bool) else "\n".join(value))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, StopIteration) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
