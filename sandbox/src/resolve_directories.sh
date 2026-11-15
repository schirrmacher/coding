# Source-only mounts operations.

prepare_directories() {
	local paths directory allowed=0
	paths=$(resolve_directories) || exit 1
	DIRECTORIES=()
	[[ -z $paths ]] || mapfile -t DIRECTORIES <<< "$paths"
	for index in "${!DIRECTORIES[@]}"; do
		[[ -e ${DIRECTORIES[$index]} ]] || {
			echo "bind source not found: ${DIRECTORIES[$index]}" >&2
			exit 1
		}
	done
	[[ ${#DIRECTORY_ARGS[@]} -le 1 ]] || {
		echo "--directory may be supplied only once" >&2
		exit 1
	}
	WORKING_DIRECTORY=$(realpath -e -- "${DIRECTORY_ARGS[0]:-$PWD}") || exit 1
    # A hidden home means the caller's current directory may not exist in the app.
    if [[ ${#DIRECTORY_ARGS[@]} == 0 ]] && config_query -e --arg app "$APP" 'any(.apps[]; .name == $app and (.mounts | index("--tmpfs")) != null)' >/dev/null; then
        WORKING_DIRECTORY=${DIRECTORIES[0]:-/tmp}
    fi
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

resolve_directories() {
	config_query -e --arg app "$APP" 'any(.apps[]; .name == $app)' >/dev/null || {
		echo "unknown app: $APP" >&2
		return 1
	}
	app_writable_directories "$APP"
}
