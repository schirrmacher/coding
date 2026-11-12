"""Pure construction of the privilege drop and ordered Bubblewrap command."""
from dataclasses import dataclass
import json
import sys


@dataclass(frozen=True)
class LaunchContext:
    namespace: str
    uid: str
    gid: str
    directory: str
    home: str
    term: str
    language: str
    app: str
    directories: str
    proxy_host: str
    proxy_port: str

    def command(self, groups):
        args = ["ip", "netns", "exec", self.namespace, *groups["apparmor"], "setpriv",
                f"--reuid={self.uid}", f"--regid={self.gid}", "--init-groups", "--reset-env", "--inh-caps=-all",
                "bwrap", "--clearenv", "--unshare-user", "--unshare-pid", *groups["ipc"],
                "--unshare-cgroup", *groups["network"], "--ro-bind", "/", "/", "--dev", "/dev",
                "--proc", "/proc", "--tmpfs", "/tmp"]
        environment = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": self.home, "TERM": self.term,
                       "LANG": self.language, "SANDBOX_APP": self.app, "SANDBOX_DIRECTORY": self.directory,
                       "SANDBOX_DIRECTORIES": self.directories, "SANDBOX_PROXY_HOST": self.proxy_host,
                       "SANDBOX_PROXY_PORT": self.proxy_port}
        for key, value in environment.items():
            args.extend(["--setenv", key, value])
        for name in ("write", "read", "gui", "mask"):
            args.extend(groups[name])
        args.extend(["--ro-bind-try", f"/etc/netns/{self.namespace}/resolv.conf", "/etc/resolv.conf",
                     *groups["config"], "--chdir", self.directory, "--cap-drop", "ALL",
                     "--new-session", "--die-with-parent"])
        override_names = groups["overrides"][1::3]
        args.extend([*groups["environment"], *groups["overrides"], "--setenv", "SANDBOX_ENV_OVERRIDES",
                     ":".join(override_names), "--", *groups["payload"]])
        return args


def main(arguments):
    context = LaunchContext(*arguments[:11])
    remaining = arguments[11:]
    groups = {}
    while remaining:
        name, count = remaining[:2]
        length = int(count)
        if length < 0 or len(remaining) < length + 2 or name in groups:
            raise ValueError("invalid launch argument group")
        groups[name] = remaining[2:2 + length]
        remaining = remaining[2 + length:]
    return context.command(groups)


if __name__ == "__main__":
    try:
        print(json.dumps(main(sys.argv[1:])))
    except (ValueError, KeyError, TypeError) as error:
        print(f"cannot plan launch: {error}", file=sys.stderr)
        sys.exit(1)
