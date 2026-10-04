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

validate_config() {
	read_config || config_error "cannot parse config: $CONFIG"
	[[ -f $CONFIG ]] || config_error "config not found: $CONFIG"
	command -v jq >/dev/null || config_error "jq is required to parse $CONFIG"
	config_query -e 'type == "object"' >/dev/null || config_error "$CONFIG: not a TOML table"

	config_query -e '.default | type == "string" and test("^[a-z][a-z0-9-]*$")' >/dev/null \
		|| config_error "$CONFIG: default must be an app name matching [a-z][a-z0-9-]*"
	config_query -e --arg default_app "$(config_query -r '.default')" \
		'any(.apps[]; .name == $default_app)' >/dev/null \
		|| config_error "$CONFIG: default names no declared app"

	config_query -e '.net.subnet | type == "string" and test("^([0-9]{1,3}\\.){3}0/24$")' >/dev/null \
		|| config_error "$CONFIG: net.subnet must be a /24 network like 10.77.0.0/24"
	config_query -e '.proxy
		| (.sni_port | type == "number" and floor == . and . > 0 and . <= 65535)
		and (.dns_port == 53)
		and (.sni_port != .dns_port)' >/dev/null \
		|| config_error "$CONFIG: proxy.sni_port must be an integer port other than 53; proxy.dns_port must be 53"

	config_query -e '.apps | type == "array" and length > 0' >/dev/null \
		|| config_error "$CONFIG: apps must be a non-empty array"
	config_query -e 'all(.apps[]; (.name | type == "string" and test("^[a-z][a-z0-9-]*$")))' >/dev/null \
		|| config_error "$CONFIG: every app name must match [a-z][a-z0-9-]* (they become namespace and profile names)"
	config_query -e '([.apps[].name] | length) == ([.apps[].name] | unique | length)' >/dev/null \
		|| config_error "$CONFIG: duplicate app names"

	config_query -e 'all(.apps[]; .endpoints | type == "array" and length > 0 and all(.[]; type == "string" and length > 0))' >/dev/null \
		|| config_error "$CONFIG: every app needs a non-empty endpoints array"
	config_query -e 'all(.apps[]; .cmd == null
		or (.cmd | type == "array" and length > 0 and all(.[]; type == "string" and length > 0)))' >/dev/null \
		|| config_error "$CONFIG: cmd must be a non-empty array of argument strings (or absent)"
	config_query -e 'all(.apps[]; .codex_home == null or
		(.codex_home | type == "string" and startswith("/") and length > 1))' >/dev/null \
		|| config_error "$CONFIG: codex_home must be an absolute directory path"
	config_query -e 'all(.apps[]; .gui == null or (.gui | type == "boolean"))' >/dev/null \
		|| config_error "$CONFIG: gui must be true or false (or absent)"
	validate_launcher_config || exit 1
}

validate_launcher_config() {
	config_query -e 'all(.apps[]; .wrapper_name == null or
		(.wrapper_name | type == "string" and test("^[a-z][a-z0-9-]*$")))' >/dev/null || {
		echo "$CONFIG: wrapper_name must match [a-z][a-z0-9-]*" >&2
		return 1
	}
	config_query -e 'all(.apps[]; .launchers == null or
		(.launchers | type == "array" and length > 0 and
			all(.[]; type == "string" and test("^[A-Za-z0-9][A-Za-z0-9_.-]*\\.desktop$"))))' >/dev/null || {
		echo "$CONFIG: launchers must contain desktop filenames without directory paths" >&2
		return 1
	}
	config_query -e '
		[.apps[] | select(.cmd != null) | .wrapper_name // .name] as $wrappers
		| ($wrappers | length) == ($wrappers | unique | length)' >/dev/null || {
		echo "$CONFIG: duplicate wrapper names" >&2
		return 1
	}
	config_query -e '
		[.apps[] | select(.cmd != null and .gui == true)
			| if .launchers == null then .name + "-sandboxed.desktop" else .launchers[] end] as $files
		| ($files | length) == ($files | unique | length)' >/dev/null || {
		echo "$CONFIG: duplicate desktop filenames" >&2
		return 1
	}
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

canonical_directories() {
	local directory
	while IFS= read -r directory; do
		realpath "$directory" || return 1
	done | awk '!seen[$0]++'
}

app_writable_directories() {
	local app=$1
	{
		app_project_directories "$app"
		app_codex_home "$app"
		app_state_directories "$app"
	} | canonical_directories
}

app_readable_directories() {
	config_query -r --arg app "$1" 'first(.apps[] | select(.name == $app)).dir.read // [] | .[]' |
		canonical_directories
}

app_private_directories() {
	config_query -r --arg app "$1" '
		first(.apps[] | select(.name == $app)) as $current
		| [$current.codex_home // empty, ($current.dir.state // [] | .[]),
		   ($current.dir.write // [] | .[]), ($current.dir.read // [] | .[])] as $granted
		| .apps[] | select(.name != $app)
		| (.codex_home // empty), (.dir.state // [] | .[])
		| select(. as $path | $granted | index($path) == null)' |
		canonical_directories
}

config_error() {
	echo "$1" >&2
	exit 1
}
