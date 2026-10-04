# Sandbox

1. `sudo sandbox up` prepares the host. `ip` creates per-app network namespaces and veth pairs. `nft` restricts traffic. `apparmor_parser` loads file policies. `systemctl` starts the DNS/TLS proxy.
2. `sudo` runs the launcher as root.
3. `ip netns exec` enters the app's network namespace.
4. `aa-exec` applies the app's AppArmor profile. Children inherit it.
5. `setpriv` restores the caller's user and groups and clears inheritable capabilities.
6. `bwrap` isolates user, PID, IPC, and cgroup namespaces. It mounts a read-only root, allowed folders, secret masks, and private `/tmp`. It drops capabilities and starts the app.
7. `nftables` redirects HTTPS to the proxy and blocks other traffic except DNS. The proxy allows exact TLS SNI hostnames from `endpoints`.

Example `sandbox/sandbox.toml`:

```toml
default = "codex"

[net]
subnet = "10.77.0.0/24"

[proxy]
sni_port = 3128
dns_port = 53

[[apps]]
name = "codex"
cmd = ["${HOME}/.local/share/codex/current/bin/codex"]
codex_home = "${HOME}/.codex"
dir.read = ["${HOME}/.agents"]
endpoints = ["api.openai.com", "chatgpt.com", "auth.openai.com"]
```

Example `~/.config/sandbox/local.toml`:

`apps` grants read/write access. `read` grants read-only access. Endpoints combine.

```toml
[[directories]]
path = "${HOME}/projects/example"
apps = ["codex"]
read = []
endpoints = ["github.com"]
```
