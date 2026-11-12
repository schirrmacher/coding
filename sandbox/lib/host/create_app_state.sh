# Source-only prepare operations.

prepare_app_state() {
	[[ ${CONFIG_SOURCE:-} == "$CONFIG" ]] || read_config || return 1
	config_query -e 'any(.apps[]; (.dir.state // [] | length) > 0)' >/dev/null || return 0
	local home
	local uid=${SUDO_UID:-$UID} gid=${SUDO_GID:-$(id -g)}
	home=$(getent passwd "$uid" | cut -d: -f6)
	setpriv --reuid="$uid" --regid="$gid" --init-groups --reset-env \
		python3 "$SCRIPT_DIR/../lib/create_app_state.py" "$home" <<< "$CONFIG_JSON"
}

validate_app_directories() {
	local app paths path
	for app in "${APPS[@]}"; do
		paths=$(app_writable_directories "$app" && app_readable_directories "$app") || return 1
		while IFS= read -r path; do
			[[ -z $path || -e $path ]] || die "app '$app': required bind source missing: $path; run applications/install $app if application setup is needed"
		done <<< "$paths"
	done
}
