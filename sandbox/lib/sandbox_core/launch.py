"""Pure construction of the privilege drop and ordered bubblewrap command."""
from dataclasses import dataclass


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
        for name in ("write", "read", "mask", "gui"):
            args.extend(groups[name])
        args.extend(["--ro-bind-try", f"/etc/netns/{self.namespace}/resolv.conf", "/etc/resolv.conf",
                     *groups["config"], "--chdir", self.directory, "--cap-drop", "ALL",
                     "--new-session", "--die-with-parent"])
        environment = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": self.home, "TERM": self.term,
                       "LANG": self.language, "SANDBOX_APP": self.app, "SANDBOX_DIRECTORY": self.directory,
                       "SANDBOX_DIRECTORIES": self.directories, "SANDBOX_PROXY_HOST": self.proxy_host,
                       "SANDBOX_PROXY_PORT": self.proxy_port}
        for key, value in environment.items():
            args.extend(["--setenv", key, value])
        # CLI overrides must follow configured values; protected mounts must follow home grants.
        args.extend([*groups["environment"], *groups["overrides"], "--", *groups["payload"]])
        return args
