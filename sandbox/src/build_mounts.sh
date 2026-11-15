# Source-only assembly of native app arguments and protected mounts.
MOUNT_SOURCES_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

prepare_mounts_and_environment() {
	NETWORK_ARGS=()
	if [[ ${OFFLINE:-0} == 1 ]] || config_query -e --arg app "$APP" 'any(.apps[]; .name == $app and .endpoints == [] and .network != "web")' >/dev/null; then
		NETWORK_ARGS=(--unshare-net)
	fi
	local paths config_path arguments
	paths=$(config_query -r '.config_directories[], .config_paths[]') || return 1
	CONFIG_ARGS=()
	while IFS= read -r config_path; do
		CONFIG_ARGS+=(--ro-bind-try "$config_path" "$config_path")
	done <<< "$paths"
	IPC_ARGS=(--unshare-ipc)
	arguments=$(config_query -c --arg app "$APP" 'first(.apps[] | select(.name == $app)).mounts') || return 1
	mapfile -d '' -t BIND_ARGS < <(jq -j '.[] + "\u0000"' <<< "$arguments")
	if [[ -n ${DISPLAY:-} ]] && config_query -e --arg app "$APP" 'first(.apps[] | select(.name == $app)).files | has("mounts.x11.args")' >/dev/null; then
		IPC_ARGS=()
		arguments=$(config_query -c --arg app "$APP" 'first(.apps[] | select(.name == $app)).mounts_x11') || return 1
		mapfile -d '' -t GUI_ARGS < <(jq -j '.[] + "\u0000"' <<< "$arguments")
	else
		GUI_ARGS=()
	fi
	READ_ARGS=()
	APP_ENV_ARGS=()
	build_mask_args "$HOME_DIR" || return 1
	local launch
	launch=$(config_query -r --arg app "$APP" 'first(.apps[] | select(.name == $app)).files["launch.sh"] // empty') || return 1
	if [[ -n $launch ]]; then
		if [[ ${#CMD[@]} == 0 ]]; then
			CMD=(/bin/sh "$launch")
		elif [[ ${CMD[0]} != /bin/sh || ${CMD[1]:-} != "$launch" ]]; then
			CMD=(/bin/sh "$launch" --sandbox-command "${CMD[@]}")
		fi
	elif [[ ${#CMD[@]} == 0 ]]; then
		CMD=(bash)
	fi
}

build_mask_args() {
	local mask paths
	paths=$(python3 "$MOUNT_SOURCES_DIR/render_secret_rules.py" masks "$1") || return 1
	MASK_ARGS=()
	while IFS= read -r mask; do
		[[ -d $mask ]] || continue
		MASK_ARGS+=(--tmpfs "$mask")
	done <<< "$paths"
	paths=$(app_private_directories "$APP") || return 1
	while IFS= read -r mask; do
		[[ -d $mask ]] || continue
		MASK_ARGS+=(--tmpfs "$mask")
	done <<< "$paths"
}
