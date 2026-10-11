# Source-only services operations.

install_proxy() {
	echo "==> proxy service"

    [[ ${CONFIG_SOURCE:-} == "$CONFIG" ]] || read_config || return 1
    local temporary runtime
    runtime=$(python3 "$SCRIPT_DIR/../lib/network_query.py" proxy "$POOL_BASE" <<< "$CONFIG_JSON") || return 1
    mkdir -p "$PROXY_DIR"
    temporary=$(mktemp "$PROXY_DIR/.apps.XXXXXX") || return 1
    printf '%s\n' "$runtime" > "$temporary"
    cp "$SCRIPT_DIR/../proxy/sandbox_proxy.py" "$PROXY_DIR/" || { rm -f "$temporary"; return 1; }
    cp -R "$SCRIPT_DIR/../proxy/sandbox_proxy_core" "$PROXY_DIR/" || { rm -f "$temporary"; return 1; }
    chmod 644 "$temporary"
    mv -f "$temporary" "$PROXY_DIR/apps.json"
	echo "==> proxy config: $PROXY_DIR/apps.json"

	if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null; then
		cp "$SCRIPT_DIR/../proxy/sandbox-proxy.service" /etc/systemd/system/
		systemctl daemon-reload
		systemctl enable --quiet sandbox-proxy.service
		systemctl restart sandbox-proxy.service
	else
		echo "    no systemd; the proxy will run in the foreground (Ctrl-C stops it)"
	fi
}

# Only the launcher receives passwordless sudo; it drops privileges before execution.

install_sudoers() {
	local user=${SUDO_USER:-} launcher temporary_file
	local rules=()
	[[ -n $user ]] || {
		echo "WARNING: no SUDO_USER; skipping sudoers setup" >&2
		return
	}
	launcher=$(realpath "$SCRIPT_DIR/../bin/sandbox")
	rules+=("$user ALL=(root) NOPASSWD: $launcher")
	rules+=("$user ALL=(root) NOPASSWD: /usr/local/bin/sandbox")
	temporary_file=$(mktemp)
	{
		echo "# Managed by sandbox up: passwordless sudo for the sandbox launcher."
		echo "# The launcher drops every privilege back to the invoking user."
		printf '%s\n' "${rules[@]}"
	} > "$temporary_file"
	if [[ -f /etc/sudoers.d/sandbox ]] \
		&& [[ $(cat /etc/sudoers.d/sandbox) == *"${rules[0]}"* ]] \
		&& [[ $(cat /etc/sudoers.d/sandbox) == *"${rules[1]}"* ]]; then
		rm -f "$temporary_file"
		echo "==> sudoers: /etc/sudoers.d/sandbox already current"
		return
	fi
	if command -v visudo >/dev/null; then
		visudo -cf "$temporary_file" >/dev/null || {
			rm -f "$temporary_file"
			die "generated sudoers rule failed visudo check"
		}
	else
		echo "WARNING: visudo not found; installing without syntax check" >&2
	fi
	install -m 0440 "$temporary_file" /etc/sudoers.d/sandbox
	rm -f "$temporary_file"
	echo "==> sudoers: installed /etc/sudoers.d/sandbox (launcher + /usr/local/bin/sandbox)"
}

# Reserve four addresses per app: host 4i+1, namespace 4i+2.
