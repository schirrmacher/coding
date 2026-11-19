# Sandbox

Run installation and host setup from a normal host terminal:

```sh
make install-sandbox
sudo sandbox up
sandbox/tests/test_sandbox.sh --installed
```

The launcher enters a per-app network namespace, applies an inherited AppArmor
profile, drops to the calling user, and starts Bubblewrap. The root filesystem is
read-only except for explicit binds. Secret masks, other-app state masks, and
protected definition mounts follow app mounts. Bubblewrap drops capabilities
before starting the payload. Apps normally use the namespace firewall and hostname-checking HTTPS proxy.
An empty endpoint file selects offline mode unless the app explicitly selects
public web networking. `--offline` disconnects either mode for one launch.

## App definitions

Apps are immediate subdirectories of `apps/`, discovered in filename order.
Their directory names are their identities. Configuration lives in these native
per-app files and their personal replacements. Shared implementation defaults
use subnet `10.77.0.0/24`, HTTPS proxy port `3128`, and DNS port `53`.

```text
sandbox/
├── run        # Run an app or dispatch up, down, status
├── install    # Generate PATH wrappers and desktop entries
├── up         # Install host confinement
├── down       # Remove host confinement
├── apps/      # Native per-app configuration
├── rules/     # Shared enforcement rules and proxy service unit
├── src/       # Shared implementation
└── tests/     # Local and installed checks
```

```text
apps/codex/
├── apparmor          # Required: native rules inside the generated profile
├── mounts.args       # Required: native Bubblewrap arguments
├── endpoints         # Required: exact hostnames; empty normally means offline
├── state             # Optional: state directories to create and isolate
├── launch.sh         # Optional: environment setup and default command
├── network           # Optional: web enables public HTTP/HTTPS browsing
├── localhost-ports   # Optional: relay selected host-local TCP services
├── wrappers          # Optional: exact PATH-wrapper names, one per line
├── mounts.x11.args   # Optional: additional arguments when DISPLAY is present
└── *.desktop         # Optional: native desktop entries with official filenames
```

For example, the two native file-access declarations for a shared read-only
installation are:

```text
# apparmor
"${HOME}/.agents/" r,
"${HOME}/.agents/**" rmk,
deny "${HOME}/.agents/**" wl,

# mounts.args
--ro-bind
${HOME}/.agents
${HOME}/.agents
```

Argument files contain one argument per line. Spaces are preserved; blank lines
and whole-line comments are ignored. Do not add shell quotes. Only `${HOME}`,
`${UID}`, `${DISPLAY}`, `${WAYLAND_DISPLAY}`, `${XAUTHORITY}`,
`${XDG_RUNTIME_DIR}`, and `${DBUS_SESSION_BUS_ADDRESS}` expand. No shell text is
evaluated. Optional bind variants are omitted when a referenced session variable is empty.
Other missing desktop variables expand to empty strings; the runtime-dir
and bus-address defaults use the calling user's `/run/user/<uid>`.

Supported arguments are native bind variants, `--dir`, `--tmpfs`, `--dev`,
`--setenv`, `--unsetenv`, and `--unshare-ipc`. Command boundaries, namespace
selection, inherited file descriptors, and privilege settings remain owned by
the launcher. App argument order is retained. CLI environment overrides follow
app arguments and the standard environment; final protection mounts follow all
app mounts.

Bubblewrap has no `--share-ipc` flag. When an app provides `mounts.x11.args` and
`DISPLAY` is set, the launcher omits its default `--unshare-ipc` so X11 MIT-SHM
can work. The file may be empty. Put `--unshare-ipc` in its replacement to retain
isolation in an X11 session. Sessions without DISPLAY remain isolated.

AppArmor files may use native `#include <sandbox/gui>`, `<sandbox/pty>`,
`<sandbox/browser>`, `<sandbox/display>`, `<sandbox/nested-network-namespace>`,
and `<sandbox/secret-service>` includes. The renderer expands
shipped includes into standalone profiles; system AppArmor abstractions remain
native includes. AppArmor path placeholders are limited to `${HOME}` and `${UID}`.
Enabling a permission include does not add mounts: declare the matching devices,
sockets, and environment explicitly in the argument files.

## State and shared protections

`state` lists absolute paths, with `${HOME}` and other supported path placeholders.
Setup creates these directories as the calling user. The inventory grants no
file access: writable mounts and AppArmor grants must both be explicit.

Other apps receive automatic denies and masks for inventoried state paths. Apps
that list the same state path share it. An explicit same-source/same-destination
`--bind` or `--ro-bind` of the exact state path also exempts that path from
automatic isolation. A broad parent bind does not exempt nested state.

Shared rules remain under `rules/`: the AppArmor base and feature fragments,
`firewall.nft`, and `secrets.toml`. Secret directories are denied and masked when
they exist; secret files receive AppArmor denies. App definitions cannot replace
these shared protections. Definitions, shared rules, launcher implementation, and their containing
directories are mounted read-only and denied writes, including beneath broad
home or project grants.

## Application installation and launch scripts

Application-specific setup lives in `../applications/` and never runs during
`make install-sandbox` or `sandbox up`. Run the relevant `applications/install APP`
command first if required. Host setup creates only declared state directories
and reports missing bind sources; it never downloads code, seeds editor profiles,
or changes application settings. Executable preparation hooks are rejected.

Launch scripts run through `/bin/sh` inside the sandbox and must support two invocations:

```sh
#!/bin/sh
set -eu
# A CLI --env value, including an empty value, wins over this default.
case ":${SANDBOX_ENV_OVERRIDES-}:" in
    *:CODEX_HOME:*) ;;
    *) export CODEX_HOME="$HOME/.codex" ;;
esac
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "$HOME/.local/share/codex/current/bin/codex" "$@"
fi
exec "$@"
```

Managed PATH wrappers pass their app identity to the launcher and forward arguments. Explicit
`sudo sandbox --app NAME command ...` invocations pass through the same environment
setup using the reserved `--sandbox-command` marker. Without a launch script,
the payload is Bash when no command is supplied; explicit commands run directly. `--env NAME=value`
and `--directory PATH` keep their existing CLI behavior. Payload launches require
`--app NAME`; administrative `up`, `down`, and `status` commands do not.

Apps with launch scripts receive a wrapper named after the app unless `wrappers`
lists different names. Native desktop entries retain their IDs, metadata, field
codes, and actions; installation rewrites their Exec commands through the managed
wrapper and preserves original entries for rollback.

## Personal replacements

Place native replacement files under `~/.config/sandbox/apps/<app>/`. A local
file replaces the corresponding public file in full; omitted files inherit.
Empty files intentionally remove public content. Local entries cannot introduce
unknown apps or replace shared protections. There is no field-specific merging.
Legacy app tables and `local.toml` are rejected; no conversion code is retained.

Changes to effective definitions, implementation, app membership, or shared rules
invalidate the installed fingerprint. App ordering determines namespace address
allocation. Run `sudo sandbox up` after policy edits, then restart apps.
The launcher refuses stale installed policy.

## Brave and network modes

### Host localhost services

`localhost-ports` lists TCP ports from 1024 through 65535, one per line; comments
and empty lines are allowed. Personal replacements use the same format and can
disable access with an empty file. OpenCode, Orca, and uv opt into port `8765`:

```sh
curl -v --max-time 10 http://127.0.0.1:8765/health
uv run python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=10).read().decode())'
```

Setup binds a loopback listener inside each opted-in namespace. A private Unix
socket connects it to a host-side relay targeting only `127.0.0.1` on the same
port. This works with Docker-published localhost ports without changing Docker
or exposing additional host services through the namespace firewall. The whole
TCP service is reachable, not just `/health`. All processes sharing an opted-in
namespace share this access; unconfigured namespaces and `--offline` launches
do not receive it. No relay socket permissions are added to application profiles.

Relays require systemd and `/usr/lib/systemd/systemd-socket-proxyd`; they run as
the invoking user with hardened services and user-owned mode-0600 Unix sockets.
`sudo sandbox up` refreshes them, and `sudo sandbox down` removes them.
`sudo sandbox status` reports listener state; it does not probe upstream health.
Occupied namespace ports fail setup. Upstream failures appear in the service
journal, and later connections recover after the container starts or restarts.
Run setup explicitly after reboot; no new boot service is enabled. Docker's
`search-search-1` can keep its existing `127.0.0.1:8765->8765/tcp` mapping.

### Public web access

Brave Browser has its own `brave` definition, PATH wrapper, and desktop entry.
Its profile is `~/.local/share/sandbox/brave`; the original browser profile stays
hidden. Its home is masked before mounting its profile, `~/Downloads`, and
`~/dev` read/write. Other personal files and application state stay hidden or
denied. Existing secret-path denies also apply, including through symlinks.
Files readable in Downloads or dev can be uploaded by a compromised browser.
The sandbox does not prevent disclosure of files explicitly made available.

Run `applications/install brave`, then install sandbox integration and host
policy. Chromium's internal sandbox stays enabled. Desktop launches use the
isolated profile rather than an existing host browser. Only display sockets and
GPU devices are shared; the desktop bus is not exposed. Prefer Wayland: X11
provides weaker isolation from other applications in the same display session.

An optional `network` file containing `web` enables public TCP ports 80 and 443.
Its endpoint file must be empty. The firewall rejects host, private, link-local,
and reserved IPv4 destinations. IPv6 is disabled in each app namespace, and
other direct traffic, including QUIC, is blocked. HTTPS falls back to TCP.
DNS uses the existing forwarder. Host IPv4 forwarding is enabled when installing
web policy; unrelated host forwarding rules remain owned by the host.

Web networking also requires `iptables`. Setup installs a managed `SANDBOX-WEB`
chain at the start of the host's `FORWARD` chain so Docker's default DROP policy
does not block browsing. Exceptions match each web app's address and veth:
outbound TCP ports 80/443 and established/related replies. The separate nftables
policy still blocks private destinations and other ports. Setup refreshes these
exceptions when app addresses change; removing web access or running
`sudo sandbox down` removes the managed chain without changing Docker's rules
or the host's default policy.

Run `sudo sandbox up` after reboot, as with the rest of the namespace setup.
Rerun it after a host firewall reset removes or reorders the forwarding rules.
Setup does not install an automatic boot or firewall-recovery service.

Without `network`, exact-hostname HTTPS restrictions remain unchanged. Empty
endpoints select offline mode. `sudo sandbox --app brave --offline COMMAND`
also selects a private network namespace regardless of the configured mode.
Close running sandbox applications before installing changed policy: setup
refuses address reassignment while affected namespaces contain processes.

Orca's endpoint list is unchanged. GitHub updates are acceptable; private updater
origins are not added. Cached release metadata identifies GitHub as the update
provider, but installed policy, live confinement, and proxy logs must be checked
on the host before attributing an update notice to network access.

## Verification

```sh
make test
make install-sandbox
sudo sandbox up
bash sandbox/tests/test_sandbox.sh --installed
```

Application setup is separate; run the relevant `applications/install APP` before
sandbox installation when needed. Host setup validates required bind sources.

`make test` aggregates application installer tests and sandbox checks. Every app
directory gets the same declaration, launch, environment-override, state-isolation,
and desktop-action contracts. Additional checks exercise declared capabilities.
Installer tests live separately with application code. No real GUI applications
are launched by the local suite.

`bash sandbox/tests/test_sandbox.sh --installed` checks every configured app on
an already prepared host; `--app NAME` filters the selection. Boundary probes
verify identity, capabilities, AppArmor inheritance, readable/writable paths,
configuration protection, state isolation, and the declared network mode.
Missing host prerequisites are reported separately from failed boundary checks.
The GUI portal probe sends a malformed request and never opens a file dialog.
