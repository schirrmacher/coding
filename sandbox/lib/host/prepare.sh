# Source-only prepare operations.

prepare_app_state() {
	[[ ${CONFIG_SOURCE:-} == "$CONFIG" ]] || read_config || return 1
	config_query -e 'any(.apps[]; (.dir.state // [] | length) > 0 or .sigrid == true or .cmd != null)' >/dev/null || return 0
	local home
	local uid=${SUDO_UID:-$UID} gid=${SUDO_GID:-$(id -g)}
	home=$(getent passwd "$uid" | cut -d: -f6)
	setpriv --reuid="$uid" --regid="$gid" --init-groups --reset-env \
		python3 "$SCRIPT_DIR/../lib/prepare_runtime.py" "$home" <<< "$CONFIG_JSON"
}

validate_app_directories() {
	# Nested writable binds would depend on mount order.
	local app directories index other_index directory
	for app in "${APPS[@]}"; do
		mapfile -t directories < <(app_writable_directories "$app" "$DEFAULT_PROJECT_DIRECTORY")
		for directory in "${directories[@]}"; do
			[[ -d $directory ]] || die "app '$app': directory '$directory' (from sandbox.toml) does not exist"
		done
		while IFS= read -r directory; do
			[[ -d $directory ]] || die "app '$app': readable directory '$directory' does not exist"
		done < <(app_readable_directories "$app")
		for index in "${!directories[@]}"; do
			for other_index in "${!directories[@]}"; do
				[[ $index == $other_index || ${directories[$other_index]}/ != "${directories[$index]}"/* ]] && continue
				die "app '$app': directory '${directories[$other_index]}' is inside '${directories[$index]}'"
			done
		done
	done
}
