"""Schema validation shared by configuration consumers."""
import ipaddress
import re

NAME = r"[a-z][a-z0-9-]*"
DESKTOP_ID = r"[A-Za-z0-9][A-Za-z0-9_.-]*\.desktop"


def validate_app_fields(app):
    if not isinstance(app, dict):
        raise ValueError("apps must be an array of tables")
    for field in ("gui", "sigrid", "pty", "browser"):
        if field in app and not isinstance(app[field], bool):
            raise ValueError(f"{field} must be true or false")
    if "cmd" in app and (not isinstance(app["cmd"], list) or not app["cmd"]
                         or any(not isinstance(arg, str) or not arg for arg in app["cmd"])):
        raise ValueError("cmd must be a non-empty array of argument strings")
    if "codex_home" in app and (not isinstance(app["codex_home"], str) or not app["codex_home"]):
        raise ValueError("codex_home must be an absolute directory path")
    env = app.get("env", {})
    if not isinstance(env, dict) or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
                                      or not isinstance(value, str) or "\0" in value
                                      for key, value in env.items()):
        raise ValueError("env must map variable names to string values")
    desktop = app.get("desktop", {})
    fields = {"enabled", "name", "id", "icon", "window_class", "terminal", "template", "terminal_app_id"}
    if not isinstance(desktop, dict) or desktop.keys() - fields:
        raise ValueError("desktop accepts only " + ", ".join(sorted(fields)))
    for key, value in desktop.items():
        if key in ("enabled", "terminal"):
            if not isinstance(value, bool):
                raise ValueError(f"desktop.{key} must be true or false")
        elif not isinstance(value, str) or "\n" in value or "\0" in value:
            raise ValueError(f"desktop.{key} must be a single-line string")
    if "terminal_app_id" in desktop and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+", desktop["terminal_app_id"]):
        raise ValueError("desktop.terminal_app_id must be a dotted application ID")
    if "id" in desktop and not re.fullmatch(DESKTOP_ID, desktop["id"]):
        raise ValueError("desktop.id must be a desktop filename without directory paths")


def validate_launchers(data):
    wrappers, desktops = [], []
    for app in data.get("apps", []):
        wrapper = app.get("wrapper_name", app["name"])
        if not isinstance(wrapper, str) or not re.fullmatch(NAME, wrapper):
            raise ValueError("wrapper_name must match [a-z][a-z0-9-]*")
        launchers = app.get("launchers")
        if launchers is not None and (not isinstance(launchers, list) or not launchers
                or any(not isinstance(item, str) or not re.fullmatch(DESKTOP_ID, item) for item in launchers)):
            raise ValueError("launchers must contain desktop filenames without directory paths")
        if "cmd" in app:
            wrappers.append(wrapper)
            from .policy import desktop_ids, desktop_enabled
            if desktop_enabled(app):
                desktops.extend(desktop_ids(app))
    if len(wrappers) != len(set(wrappers)):
        raise ValueError("duplicate wrapper names")
    if len(desktops) != len(set(desktops)):
        raise ValueError("duplicate desktop filenames")


def validate_config(data):
    apps = data.get("apps")
    if not isinstance(apps, list) or not apps:
        raise ValueError("apps must be a non-empty array")
    names = [app.get("name") for app in apps]
    if any(not isinstance(name, str) or not re.fullmatch(NAME, name) for name in names):
        raise ValueError("every app name must match [a-z][a-z0-9-]*")
    if len(names) != len(set(names)):
        raise ValueError("duplicate app names")
    if data.get("default") not in names:
        raise ValueError("default names no declared app")
    try:
        subnet = ipaddress.IPv4Network(data["net"]["subnet"])
        if subnet.prefixlen != 24:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise ValueError("net.subnet must be a /24 IPv4 network") from None
    ports = data.get("proxy", {})
    port = ports.get("sni_port")
    if type(port) is not int or not 1 <= port <= 65535 or port == 53 or ports.get("dns_port") != 53:
        raise ValueError("proxy.sni_port must be an integer port other than 53; proxy.dns_port must be 53")
    if len(apps) > 64:
        raise ValueError("subnet supports at most 64 apps")
    for app in apps:
        validate_app_fields(app)
        endpoints = app.get("endpoints")
        if not isinstance(endpoints, list) or any(not isinstance(item, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", item) for item in endpoints):
            raise ValueError("every app needs an endpoints array of hostnames (empty means offline)")
    validate_launchers(data)
