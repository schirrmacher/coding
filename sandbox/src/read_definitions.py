"""Load effective native per-app files and shared enforcement defaults."""
import hashlib
import json
import os
import pwd
import re
from pathlib import Path
from dataclasses import dataclass
import ipaddress

NAME = r"[a-z][a-z0-9-]*"
FILES = {"apparmor", "mounts.args", "mounts.x11.args", "endpoints", "state", "launch.sh", "network", "wrappers", "localhost-ports"}
VARIABLES = {"HOME", "UID", "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"}
# Only mount, environment and IPC options belong in per-app argument files.
ARITY = {"--bind": 2, "--ro-bind": 2, "--bind-try": 2, "--ro-bind-try": 2,
         "--dev-bind": 2, "--dev-bind-try": 2, "--setenv": 2, "--unsetenv": 1,
         "--dir": 1, "--tmpfs": 1, "--dev": 1, "--unshare-ipc": 0}


def lines(text):
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def context(home):
    uid = str(os.environ.get("SUDO_UID", os.getuid()))
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}"
    return {**{key: os.environ.get(key, "") for key in VARIABLES}, "HOME": home, "UID": uid,
            "XDG_RUNTIME_DIR": runtime,
            "DBUS_SESSION_BUS_ADDRESS": os.environ.get("DBUS_SESSION_BUS_ADDRESS") or f"unix:path={runtime}/bus"}


def expand(text, values):
    def replacement(match):
        key = match[1]
        if key not in VARIABLES or key not in values:
            raise ValueError(f"unsupported placeholder: ${{{key}}}")
        return values[key]
    result = re.sub(r"\$\{([^}]+)\}", replacement, text)
    if "${" in result or "\0" in result:
        raise ValueError("invalid placeholder or NUL in rule data")
    return result


def arguments(text, values):
    raw_args = lines(text)
    args = [expand(line, values) for line in raw_args]
    grants = {"write": [], "read": []}
    index = 0
    while index < len(args):
        option = args[index]
        if option not in ARITY or index + ARITY[option] >= len(args):
            raise ValueError(f"invalid or unsupported Bubblewrap option: {option}")
        count = ARITY[option]
        operands = args[index + 1:index + count + 1]
        # Optional desktop sockets disappear when a session variable is unset.
        raw_operands = raw_args[index + 1:index + count + 1]
        missing = any(not values[match[1]] for operand in raw_operands
                      for match in re.finditer(r"\$\{([^}]+)\}", operand))
        if option.endswith("-try") and missing:
            del args[index:index + count + 1]
            del raw_args[index:index + count + 1]
            continue
        if "bind" in option:
            if any(not Path(path).is_absolute() or "\n" in path for path in operands):
                raise ValueError("bind paths must be absolute")
            source, destination = operands
            if source == destination and option in ("--bind", "--ro-bind"):
                grants["read" if option == "--ro-bind" else "write"].append(str(Path(source).resolve()))
        elif option in ("--dir", "--tmpfs", "--dev") and not Path(operands[0]).is_absolute():
            raise ValueError("mount paths must be absolute")
        elif option in ("--setenv", "--unsetenv") and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", operands[0]):
            raise ValueError("invalid environment variable name")
        index += count + 1
    return args, grants


def apparmor(text, rules, home, stack=()):
    result = []
    for line in text.splitlines():
        match = re.fullmatch(r'\s*#include\s+<sandbox/([a-z][a-z0-9-]*)>\s*', line)
        if match:
            name = match[1]
            if name in stack:
                raise ValueError("recursive sandbox AppArmor include")
            result.append(apparmor((rules / "apparmor" / name).read_text(), rules, home, (*stack, name)))
        else:
            # AppArmor placeholders expand to literal path operands in quoted rules.
            result.append(expand(line, {key: context(home)[key] for key in ("HOME", "UID")}))
    return "\n".join(result) + "\n"


RULES = Path(__file__).resolve().parents[1] / "rules"


def user_home():
    return pwd.getpwuid(int(os.environ.get("SUDO_UID", os.getuid()))).pw_dir


def read_config(path, local_path=None, home=None):
    path = Path(path).resolve(strict=True)
    home = str(home) if home is not None else user_home()
    if not path.is_dir():
        raise ValueError(f"definition root is not a directory: {path}")
    data = {"net": {"subnet": "10.77.0.0/24"},
            "proxy": {"sni_port": 3128, "dns_port": 53}}
    public = path / "apps"
    local = Path(local_path) if local_path is not None else Path(home) / ".config/sandbox/apps"
    old_local = Path(home) / ".config/sandbox/local.toml"
    if local_path is None and old_local.exists():
        raise ValueError(f"{old_local}: local.toml is not supported; use native replacements under ~/.config/sandbox/apps/")
    if local.is_file():
        raise ValueError(f"{local}: local TOML is not supported; use a directory of native app replacements")
    runtime = Path(__file__).resolve().parents[1]
    implementation = runtime / "src"
    entrypoints = [runtime / name for name in ("run", "install", "up", "down")]
    directories = [public, local, RULES, implementation]
    if not public.is_dir():
        raise ValueError(f"missing app directory: {public}")
    if local.exists():
        if not local.is_dir():
            raise ValueError(f"not an app directory: {local}")
    names = sorted(child.name for child in public.iterdir() if child.is_dir())
    if not names:
        raise ValueError("apps directory must contain at least one app")
    if local.is_dir():
        unknown = {child.name for child in local.iterdir()} - set(names)
        if unknown:
            raise ValueError(f"unknown local apps: {', '.join(sorted(unknown))}")
    sources = {}
    apps = []
    values = context(home)
    for name in names:
        if not re.fullmatch(NAME, name):
            raise ValueError("every app name must match [a-z][a-z0-9-]*")
        public_app, local_app = public / name, local / name
        files = {}
        for directory in (public_app, local_app):
            if not directory.exists():
                continue
            if not directory.is_dir():
                raise ValueError(f"not an app directory: {directory}")
            directories.append(directory)
            for source in sorted(directory.iterdir()):
                if source.name not in FILES and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.desktop", source.name):
                    raise ValueError(f"unknown app file: {source}")
                if not source.is_file():
                    raise ValueError(f"not a regular app file: {source}")
                files[source.name] = str(source.resolve(strict=True))
        for required in ("apparmor", "mounts.args", "endpoints"):
            if required not in files:
                raise ValueError(f"{name}: missing {required}")
        texts = {key: Path(source).read_text() for key, source in files.items()}
        sources.update({source: texts[key] for key, source in files.items()})
        mounts, grants = arguments(texts["mounts.args"], values)
        x11, xgrants = arguments(texts.get("mounts.x11.args", ""), values)
        for mode in grants:
            grants[mode] = list(dict.fromkeys([*grants[mode], *xgrants[mode]]))
        state = [expand(line, values) for line in lines(texts.get("state", ""))]
        if any(not Path(item).is_absolute() for item in state):
            raise ValueError(f"{name}: state paths must be absolute")
        if state:
            grants["state"] = list(dict.fromkeys(str(Path(item).resolve()) for item in state))
        endpoints = list(dict.fromkeys(line.lower().rstrip(".") for line in lines(texts["endpoints"])))
        if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", host) for host in endpoints):
            raise ValueError(f"{name}: endpoints must be hostnames")
        network = lines(texts.get("network", ""))
        if network not in ([], ["web"]):
            raise ValueError(f"{name}: network must be empty or web")
        mode = "web" if network else "restricted"
        if mode == "web" and endpoints:
            raise ValueError(f"{name}: web network cannot have endpoint entries")
        raw_ports = lines(texts.get("localhost-ports", ""))
        if any(not re.fullmatch(r"[0-9]+", port) or not 1024 <= int(port) <= 65535 for port in raw_ports):
            raise ValueError(f"{name}: localhost-ports must contain TCP ports between 1024 and 65535")
        localhost_ports = list(dict.fromkeys(int(port) for port in raw_ports))
        wrappers = lines(texts.get("wrappers", name)) if "launch.sh" in files else []
        if any(not re.fullmatch(NAME, wrapper) for wrapper in wrappers):
            raise ValueError(f"{name}: invalid wrapper name")
        app = {"name": name, "files": files, "mounts": mounts, "mounts_x11": x11,
               "dir": grants, "endpoints": endpoints, "network": mode, "wrappers": wrappers, "localhost_ports": localhost_ports,
               "apparmor": apparmor(texts["apparmor"], RULES, home),
               "desktops": {key: expand(value, values) for key, value in texts.items() if key.endswith(".desktop")}}
        if "launch.sh" in files:
            app["cmd"] = ["/bin/sh", files["launch.sh"]]
        apps.append(app)
    for source in sorted(RULES.rglob("*")):
        if source.is_file():
            sources[str(source.resolve())] = source.read_text()
    # Writable project binds must not allow payloads to replace privileged launcher code.
    for source in [*entrypoints, *sorted(implementation.rglob("*"))]:
        if source.is_file() and "__pycache__" not in source.parts:
            sources[str(source.resolve())] = source.read_text()
    data.update(apps=apps, config_paths=list(sources),
                config_directories=list(dict.fromkeys(str(directory.resolve()) for directory in directories)))
    # Session variables affect launch arguments, not the installed policy identity.
    identity = {"network": {"net": data["net"], "proxy": data["proxy"]}, "sources": sources, "directories": data["config_directories"],
                "home": home, "uid": values["UID"]}
    data["policy_fingerprint"] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return data




def desktop_enabled(app):
    return bool(app.get("desktops"))


def desktop_ids(app):
    return tuple(app.get("desktops", {}))


@dataclass(frozen=True)
class AppPolicy:
    name: str
    writable: tuple[str, ...]
    readable: tuple[str, ...]
    private: tuple[str, ...]

    @classmethod
    def from_config(cls, data, name):
        app = next(app for app in data["apps"] if app["name"] == name)
        dirs = app["dir"]
        granted = set([*dirs["write"], *dirs["read"], *dirs.get("state", [])])
        private = dict.fromkeys(path for other in data["apps"] if other["name"] != name
                                for path in other["dir"].get("state", []) if path not in granted)
        return cls(name, tuple(dirs["write"]), tuple(dirs["read"]), tuple(private))




def validate_launchers(data):
    for app in data["apps"]:
        if app["desktops"] and not app["wrappers"]:
            raise ValueError(f'desktop app has no command wrapper: {app["name"]}')
    wrappers = [wrapper for app in data["apps"] for wrapper in app["wrappers"]]
    desktops = [desktop for app in data["apps"] for desktop in app["desktops"]]
    if len(wrappers) != len(set(wrappers)):
        raise ValueError("duplicate wrapper names")
    if len(desktops) != len(set(desktops)):
        raise ValueError("duplicate desktop filenames")


def validate_config(data):
    names = [app["name"] for app in data["apps"]]
    if len(names) > 64:
        raise ValueError("subnet supports at most 64 apps")
    validate_launchers(data)




@dataclass(frozen=True)
class NetworkAllocation:
    host: str
    namespace: str

    @classmethod
    def at(cls, pool, index):
        if not 0 <= index < 64:
            raise ValueError("network allocation index must be between 0 and 63")
        base = int(ipaddress.IPv4Address(pool + ".0"))
        return cls(str(ipaddress.IPv4Address(base + 4 * index + 1)),
                   str(ipaddress.IPv4Address(base + 4 * index + 2)))


def proxy_config(data, pool):
    apps = []
    for index, app in enumerate(data["apps"]):
        addresses = NetworkAllocation.at(pool, index)
        apps.append({"ip": addresses.host, "netns_ip": addresses.namespace,
                     "name": app["name"], "endpoints": app["endpoints"], "network": app.get("network", "restricted")})
    return {"policy_fingerprint": data["policy_fingerprint"], "net": data.get("net", {}),
            "proxy": data.get("proxy", {}), "apps": apps}


def main():
    import sys
    operation, *args = sys.argv[1:]
    if operation == "query":
        query, *args = args
        data = json.load(sys.stdin)
        if query == "validate":
            validate_config(data)
        elif query == "validate-launchers":
            validate_launchers(data)
        elif query in ("desktops", "desktop-apps"):
            for app in data["apps"]:
                if args and app["name"] != args[0]:
                    continue
                if query == "desktops":
                    print("\n".join(desktop_ids(app)))
                elif desktop_enabled(app):
                    print(app["name"])
        elif query == "apparmor":
            print(next(app["apparmor"] for app in data["apps"] if app["name"] == args[0]), end="")
        else:
            print("\n".join(getattr(AppPolicy.from_config(data, args[0]), query)))
    elif operation == "network":
        query, pool, *args = args
        if query == "proxy":
            print(json.dumps(proxy_config(json.load(sys.stdin), pool)))
        else:
            print(getattr(NetworkAllocation.at(pool, int(args[0])), query))
    else:
        print(json.dumps(read_config(operation, *args), allow_nan=False))


if __name__ == "__main__":
    import sys
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
        print(f"cannot read definitions: {error}", file=sys.stderr)
        sys.exit(1)
