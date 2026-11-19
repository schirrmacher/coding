# Source-only status operations.

cmd_status() {
	local -a apps=()
	mapfile -t apps < <(config_query -r '.apps[].name')

	print_app_rows "${apps[@]}"
	print_firewall_status
	print_apparmor_status "${apps[@]}"
	print_proxy_status
	print_localhost_status
	print_sudoers_status
}

print_app_rows() {
	local -a apps=("$@")
	local app row ip endpoint_count netns

	printf '%-10s %-6s %-13s %s\n' app netns ip endpoints
	for app in "${apps[@]}"; do
		if ip netns list 2>/dev/null | grep -q "^sandbox-$app "; then
			netns=up
		else
			netns=down
		fi
		row=""
		[[ -r $PROXY_CONFIG ]] && row=$(jq -r --arg app "$app" \
			'first(.apps[] | select(.name == $app)) | .ip // empty' "$PROXY_CONFIG")
		endpoint_count=$(config_query -r --arg app "$app" \
			'first(.apps[] | select(.name == $app)) | if .network == "web" then "public web" else (.endpoints | length) end')
		if [[ -n $row ]]; then
			ip=$row
		else
			ip=-
			endpoint_count+=" (config)"
		fi
		printf '%-10s %-6s %-13s %s\n' "$app" "$netns" "$ip" "$endpoint_count"
	done
}

print_firewall_status() {
	if nft list table ip sandbox >/dev/null 2>&1; then
		echo "nftables: filtered (table ip sandbox, pool $(config_query -r '.net.subnet'))"
	else
		echo "nftables: not installed"
	fi
}

print_apparmor_status() {
	local -a apps=("$@")
	local app loaded=0
	local profiles=${APPARMOR_PROFILES:-/sys/kernel/security/apparmor/profiles}
	if [[ ! -r $profiles ]]; then
		echo "apparmor: enforcing profiles unavailable"
		return
	fi

	for app in "${apps[@]}"; do
		grep -qxF "sandbox-$app (enforce)" "$profiles" 2>/dev/null && loaded=$((loaded + 1))
	done
	echo "apparmor: $loaded/${#apps[@]} profiles loaded"
}

print_proxy_status() {
	local pid since

	if [[ -d /run/systemd/system ]] && systemctl is-active --quiet sandbox-proxy.service 2>/dev/null; then
		pid=$(systemctl show -p MainPID --value sandbox-proxy.service)
		since=$(systemctl show -p ActiveEnterTimestamp --value sandbox-proxy.service)
		if [[ -n $pid && -n $since ]]; then
			echo "proxy:    active (pid $pid, since $since)"
		else
			echo "proxy:    active"
		fi
	elif [[ -x $PROXY_DIR/proxy.py ]]; then
		echo "proxy:    not running (runtime present; sudo sandbox up starts it)"
	else
		echo "proxy:    not installed"
	fi
}

print_sudoers_status() {
	if [[ -f /etc/sudoers.d/sandbox ]]; then
		echo "sudoers:  installed"
	else
		echo "sudoers:  not installed"
	fi
}

print_localhost_status() {
    local app port state
    while IFS=$'\t' read -r app port; do
        [[ -n $app ]] || continue
        state=inactive
        if systemctl is-active --quiet "sandbox-localhost-app-$app-$port.service" 2>/dev/null \
            && systemctl is-active --quiet "sandbox-localhost-host-$port.socket" 2>/dev/null; then
            state=active
        fi
        printf 'localhost: %s 127.0.0.1:%s %s\n' "$app" "$port" "$state"
    done < <(config_query -r '.apps[] | .name as $app | (.localhost_ports // [])[] | [$app, .] | @tsv')
}
