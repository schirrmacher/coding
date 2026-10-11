# Keep one parsed TOML snapshot per invocation; the proxy config stays JSON.
CONFIG_LOADER=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/load_config.py

canonical_config_path() {
	local path
	path=$(realpath -e -- "$CONFIG") || return 1
	[[ -f $path ]] || {
		echo "configuration is not a regular file: $CONFIG" >&2
		return 1
	}
	printf '%s\n' "$path"
}

read_config() {
	CONFIG_JSON=$(python3 "$CONFIG_LOADER" "$CONFIG" ${LOCAL_CONFIG:+"$LOCAL_CONFIG"}) || return 1
	CONFIG_SOURCE=$CONFIG
}

config_paths() {
	config_query -r '.config_paths[]'
}

config_query() {
	[[ ${CONFIG_SOURCE:-} == "$CONFIG" ]] || read_config || return 1
	jq "$@" <<< "$CONFIG_JSON"
}

policy_query() {
    [[ ${CONFIG_SOURCE:-} == "$CONFIG" ]] || read_config || return 1
    python3 "${CONFIG_LOADER%/*}/policy_query.py" "$@" <<< "$CONFIG_JSON"
}

validate_config() {
    read_config || config_error "cannot parse config: $CONFIG"
    policy_query validate || config_error "$CONFIG: invalid configuration"
}

validate_launcher_config() {
    policy_query validate-launchers
}

app_project_directories() {
	config_query -r --arg app "$1" 'first(.apps[] | select(.name == $app)).dir.write // [] | .[]'
}

app_codex_home() {
	config_query -r --arg app "$1" 'first(.apps[] | select(.name == $app)).codex_home // empty'
}

app_state_directories() {
	config_query -r --arg app "$1" 'first(.apps[] | select(.name == $app)).dir.state // [] | .[]'
}

app_writable_directories() {
    policy_query writable "$1" | sed '/^$/d'
}

app_readable_directories() {
    policy_query readable "$1" | sed '/^$/d'
}

app_private_directories() {
    policy_query private "$1" | sed '/^$/d'
}

config_error() {
	echo "$1" >&2
	exit 1
}

desktop_filenames() {
    policy_query desktops ${1:+"$1"}
}
