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

Local entries match publicly declared apps by `name`. `dir.read`, `dir.write`,
`dir.state`, and `endpoints` append to the public lists; duplicates are removed.
`env` and `desktop` merge by key. `cmd`, `gui`, `pty`, `wrapper_name`, `launchers`,
`codex_home`, and `sigrid` replace public values
when supplied. Omitted settings inherit public values. Global settings remain
public-only. Local read/write directories must exist; state directories are
created during setup.

```toml
[[apps]]
name = "codex"
dir.write = ["${HOME}/projects/example"]
endpoints = ["github.com"]
```

The former `[[directories]]` format is no longer supported. Move each directory's
`apps` grants into the corresponding app's `dir.write` list and its `read` grants
into `dir.read`. Copy its endpoints to each app that received access.

## SIGRID in project shells

Codex and OpenCode expose the installed SIGRID CLI through a dedicated runtime
launcher. Install SIGRID first, then run `make install-sandbox`, `sudo sandbox up`,
and restart the agent. This applies to every project granted to those apps.

The `sigrid = true` app setting enables access to the desktop session bus and
Secret Service. Its `dir.read` grants the installed package and runtime launcher;
`dir.state` grants `~/.config/sigrid`, which stores group names and selections.
The keyring files remain masked. Apps without this setting receive no new
Secret Service permissions. A running desktop session is required.

```sh
sigrid --help
```

SIGRID's executable prints exports; noninteractive agent shells do not load the
host's SIGRID shell function. Capture and evaluate the exports in the same shell
as the project command:

```sh
sigrid_exports="$(sigrid)" && eval "$sigrid_exports" && ./run-project.sh
```

## Desktop apps

Run these commands from a normal host terminal, outside the sandbox:

```sh
make install-apps
sudo sandbox up
sandbox/tests/test_sandbox.sh --installed --app zed --app herdr --app photocraft --app vectorcraft --app designcraft
```

App definitions belong in `sandbox.toml`; machine-specific grants belong in
`~/.config/sandbox/local.toml`. The installer does not edit either configuration.
It verifies SHA-256 digests for Zed v1.23.2, its non-setuid bubblewrap helper,
Herdr v0.9.3, PhotoCraft v0.7.0, VectorCraft v0.9.0, and DesignCraft v0.6.0.
Downloads can be reused with `python3 sandbox/lib/install_apps.py
--download-dir /path/to/downloads`, followed by `make install-sandbox`.

Zed runs through the `zed` wrapper and its desktop launcher. Its empty
`endpoints = []` means offline: bubblewrap creates a private network namespace
with only loopback, isolating IPv4, IPv6, and DNS. No DNS listener forwards its queries.
Missing endpoint lists remain invalid. Extensions and language servers must be
installed separately on the host before they can be used offline.

PhotoCraft, VectorCraft, and DesignCraft use the same offline policy. Their
AppImages live in `~/Applications`; the generated command and desktop launchers
enter the sandbox. The installer extracts their bundled icons for the application
menu. Craft launchers use the apps' official desktop IDs and replace original
entries after backing them up in `~/.local/share/sandbox/original-desktop-entries`.
Old managed duplicates are removed. Launcher names omit the sandbox suffix;
the command wrappers still enforce sandboxing. PhotoCraft's automatic desktop
integration is disabled inside the sandbox to prevent it replacing the launcher. Herdr also has a terminal launcher. They can open, save, and export
throughout the home directory.
Secret masks, other agents' private-state protections, and read-only sandbox
configuration still apply. Home access also covers the apps' own settings, so
they do not need nested writable state grants.

Herdr runs through the `herdr` wrapper. Its terminals and coding agents inherit
one policy with the combined Claude, Codex, and OpenCode endpoint allowlists.
Installed agent commands are linked directly into Herdr's private `bin` directory;
they do not invoke the host's `sudo` wrappers. Herdr's app definition supplies the
shared environment and separate state paths. Claude is exposed only if its app
declaration supplies an installed command; this installer does not install agents.

Herdr's settings and separate agent state live under
`~/.local/share/sandbox/herdr`. Authenticate agents and configure their providers
inside Herdr; host credentials are not copied. SIGRID's host keyring integration
is not exposed inside this policy. Herdr uses a private socket in `/tmp` and the
existing per-launch PID namespace. Detaching ends the live sandbox session;
background persistence and reconnecting across launches are not supported.

GUI apps receive GPU device access and read-only driver metadata. X11 apps
share the host IPC namespace so MIT-SHM can communicate with the display
server; CLI apps and GUI sessions without DISPLAY keep IPC isolation.

## Extending an app

Keep app policy in `sandbox.toml` and personal overrides in
`~/.config/sandbox/local.toml`. No other file supplies configuration.
`apps.json` is generated host runtime state, checked against the effective policy
fingerprint at launch.

```toml
[[apps]]
name = "drawing"
cmd = ["${HOME}/Applications/drawing", "--foreground"]
gui = true
endpoints = []
dir.write = ["${HOME}/Pictures"]
env.RENDER_MODE = "local"
desktop.enabled = true
desktop.id = "org.example.Drawing.desktop"
desktop.name = "Drawing"
desktop.icon = "org.example.Drawing"
desktop.window_class = "org.example.Drawing"
desktop.terminal = false
```

`env` values are strings; `${HOME}` expands to the invoking account's home.
Local keys override public keys, and `--env NAME=value` overrides configured
values. Existing command argument vectors are preserved verbatim, including
literal arguments containing `=`. For new entries, put environment assignments
in `env` rather than a `/usr/bin/env` command prefix.

`desktop.template` optionally names a desktop template; `{id}` expands to the
current launcher filename. Its file arguments and actions are retained.
`launchers` can specify several desktop filenames; otherwise `desktop.id` is
used. Desktop entries invoke their own managed command wrapper. `pty = true`
grants process inspection and pseudoterminals for terminal supervisors such as
Herdr. It does not grant network or additional file access.

## Reviewing the implementation

The entrypoints retain the existing CLI and Make targets. Review their delegates
in this order:

| Piece | Responsibility |
| --- | --- |
| `lib/sandbox_core/config.py`, `schema.py` | Read, merge, validate, canonicalize and fingerprint the two TOML files |
| `lib/sandbox_core/policy.py` | Derive effective grants, private state, environment, capabilities and desktop identity |
| `lib/sandbox_core/launch.py`, `lib/launch/` | Build an ordered argument vector, inspect host prerequisites, then execute it |
| `lib/sandbox_core/desktop.py`, `lib/install/` | Render desktop actions, preserve originals, generate wrappers and remove managed stale entries |
| `lib/prepare_runtime.py`, `prepare_*.py` | One preparation entrypoint and specific installation adapters |
| `lib/sandbox_core/network.py`, `lib/host/` | Shared address allocation, host networking, policy installation and services |
| `proxy/sandbox_proxy_core/` | TLS parsing and relay, DNS forwarding, and runtime configuration |

The Python launch planner performs no host operations. Argument groups carry
explicit lengths and are serialized as JSON, then read into Bash arrays; no
shell text is evaluated. Config mounts come after writable grants and masks.
Offline launches unshare networking; X11 alone shares the display server's IPC
namespace. AppArmor status counts enforcing profiles from the kernel, not files
left in `/etc/apparmor.d`.

`lib/sandbox_core/legacy.py` retains presentation defaults for existing
installations. New apps declare their metadata in TOML. After changing the
configuration, run from a normal host terminal at the repository root:

```sh
make install-sandbox
sudo sandbox up
sandbox/tests/test_sandbox.sh --installed --app zed --app photocraft --app vectorcraft --app designcraft --app herdr
```

Changing the effective TOML invalidates the installed fingerprint until
`sandbox up` regenerates the host policy. The running sandbox protects its own
TOML files against writes; edit these files from a normal host terminal.

Zed preparation installs its official icon as `dev.zed.Zed` and disables both
telemetry metrics and diagnostics. It preserves unrelated settings and saves the
first original as `settings.json.pre-sandbox`. Zed remains offline. FileChooser
portal access only selects paths; the file policy still controls which selected
files Zed can read and write. Selecting a file outside its grants does not grant
access automatically.

Run local checks with `bash sandbox/tests/test_sandbox.sh`. Installed checks are
reported separately, and either stage failing makes the overall result fail.

Installed GUI checks also send an intentionally malformed `FileChooser.OpenFile`
request. Only the portal's `InvalidArgs` response passes; AppArmor denial or an
unavailable portal fails. This tests the actual method permission without opening
a dialog or granting access to a file. It does not verify the dialog's UI or make
files outside configured grants readable.

Herdr's desktop launcher opens a dedicated GNOME Terminal server with the
`dev.herdr.Herdr` application identity and official logo. Its D-Bus activation
service is installed with the launcher. Ordinary terminal windows keep their
identity; running `herdr` in an existing terminal keeps that terminal's dock icon.
Re-pin Herdr after regenerating the launchers if the dock still contains its old
launcher. `desktop.terminal_app_id` enables this behavior for another terminal app.
