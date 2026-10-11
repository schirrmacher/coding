# Source-only mounts operations.

prepare_directories() {
	local paths directory allowed=0
	paths=$(resolve_directories) || exit 1
	DIRECTORIES=()
	[[ -z $paths ]] || mapfile -t DIRECTORIES <<< "$paths"
	for index in "${!DIRECTORIES[@]}"; do
		[[ -d ${DIRECTORIES[$index]} ]] || {
			echo "directory not found: ${DIRECTORIES[$index]}" >&2
			exit 1
		}
	done
	[[ ${#DIRECTORY_ARGS[@]} -le 1 ]] || {
		echo "--directory may be supplied only once" >&2
		exit 1
	}
	WORKING_DIRECTORY=$(realpath -e -- "${DIRECTORY_ARGS[0]:-$PWD}") || exit 1
	[[ -d $WORKING_DIRECTORY ]] || { echo "not a directory: $WORKING_DIRECTORY" >&2; exit 1; }
	if [[ ${#DIRECTORY_ARGS[@]} -gt 0 ]]; then
		paths=$(app_readable_directories "$APP") || exit 1
		while IFS= read -r directory; do
			[[ -n $directory ]] || continue
			if [[ $WORKING_DIRECTORY == "$directory" || $WORKING_DIRECTORY/ == "$directory/"* ]]; then
				allowed=1
			fi
		done < <(printf '%s\n' "${DIRECTORIES[@]}" "$paths")
		[[ $allowed == 1 ]] || { echo "directory not allowed for app '$APP': $WORKING_DIRECTORY" >&2; exit 1; }
	fi

	HOME_DIR=$(getent passwd "$SUDO_UID" | cut -d: -f6)
	[[ -n $HOME_DIR ]] || {
		echo "cannot resolve home for uid $SUDO_UID" >&2
		exit 1
	}
}

prepare_mounts_and_environment() {
	CONFIG_PATH=$(canonical_config_path) || exit 1
	NETWORK_ARGS=()
	if config_query -e --arg app "$APP" 'any(.apps[]; .name == $app and .endpoints == [])' >/dev/null; then
		NETWORK_ARGS=(--unshare-net)
	fi
	local paths config_path
	paths=$(config_paths) || exit 1
	CONFIG_ARGS=()
	while IFS= read -r config_path; do
		CONFIG_ARGS+=(--ro-bind "$config_path" "$config_path")
	done <<< "$paths"
	IPC_ARGS=(--unshare-ipc)
	GUI=$(config_query -r --arg app "$APP" 'first(.apps[] | select(.name == $app) | .gui // false)')
	if [[ $GUI == true ]]; then
		build_gui_args
	else
		GUI_ARGS=()
	fi

	BIND_ARGS=()
	for directory in "${DIRECTORIES[@]}"; do
		BIND_ARGS+=(--bind "$directory" "$directory")
	done

	APP_ENV_ARGS=()
	local codex_home
	codex_home=$(app_codex_home "$APP")
	if [[ -n $codex_home ]]; then
		APP_ENV_ARGS+=(--setenv CODEX_HOME "$(realpath "$codex_home")")
	fi
	local env_key env_value
	while IFS= read -r -d '' env_key && IFS= read -r -d '' env_value; do
		APP_ENV_ARGS+=(--setenv "$env_key" "$env_value")
	done < <(policy_query environment "$APP")
	READ_ARGS=()
	while IFS= read -r directory; do
		READ_ARGS+=(--ro-bind "$directory" "$directory")
	done < <(app_readable_directories "$APP")

	if config_query -e --arg app "$APP" 'any(.apps[]; .name == $app and .sigrid == true)' >/dev/null; then
		build_sigrid_args "/run/user/$SUDO_UID/bus" || return 1
	fi
	build_mask_args "$HOME_DIR"
}

build_sigrid_args() {
	local bus=$1
	[[ -S $bus ]] || {
		echo "SIGRID requires the desktop session bus at $bus" >&2
		return 1
	}
	READ_ARGS+=(--ro-bind "$bus" "$bus")
	APP_ENV_ARGS+=(--setenv DBUS_SESSION_BUS_ADDRESS "unix:path=$bus")
}

resolve_directories() {
	config_query -e --arg app "$APP" 'any(.apps[]; .name == $app)' >/dev/null || {
		echo "unknown app: $APP" >&2
		return 1
	}
	app_writable_directories "$APP"
}

build_mask_args() {
	local mask
	local masks=(
		.ssh .gnupg .aws .kube .mozilla
		.config/google-chrome .config/chromium
		.password-store .local/share/keyrings
	)
	MASK_ARGS=()
	for mask in "${masks[@]}"; do
		[[ -d $1/$mask ]] || continue
		MASK_ARGS+=(--tmpfs "$1/$mask")
	done
	while IFS= read -r mask; do
		[[ -d $mask ]] || continue
		MASK_ARGS+=(--tmpfs "$mask")
	done < <(app_private_directories "$APP")
}

build_gui_args() {
	GUI_ARGS=()
	# X11 MIT-SHM must share the display server's System V IPC namespace.
	[[ -z ${DISPLAY:-} ]] || IPC_ARGS=()
	local variable
	for variable in DISPLAY WAYLAND_DISPLAY XAUTHORITY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS; do
		[[ -n ${!variable:-} ]] || continue
		GUI_ARGS+=(--setenv "$variable" "${!variable}")
	done
    if [[ -z ${DBUS_SESSION_BUS_ADDRESS:-} && -S /run/user/$SUDO_UID/bus ]]; then
        GUI_ARGS+=(--setenv DBUS_SESSION_BUS_ADDRESS "unix:path=/run/user/$SUDO_UID/bus")
    fi
	# AppImages need extraction because FUSE is unavailable inside.
	GUI_ARGS+=(--setenv APPIMAGE_EXTRACT_AND_RUN 1)
	GUI_ARGS+=(
		--bind-try /tmp/.X11-unix /tmp/.X11-unix
		--bind-try "/run/user/$SUDO_UID" "/run/user/$SUDO_UID"
		--dev-bind-try /dev/dri /dev/dri
	)
}
