# Source-only desktop operations.

write_desktop_entry() {
	local app=$1
	local desktop_file
	local -a launchers=()
	mapfile -t launchers < <(config_query -r --arg app "$app" \
		'first(.apps[] | select(.name == $app)).launchers // [] | .[]')
	if [[ ${#launchers[@]} -gt 0 ]]; then
		for desktop_file in "${launchers[@]}"; do
			write_desktop_override "$app" "$desktop_file" || return 1
		done
		return 0
	fi

	local source_entry name icon startup_wm_class terminal=false prefix rendered metadata wrapper_name
	local -a command=()
	mapfile -t command < <(app_cmd "$app")
	local path="$DESKTOP_DIR/$(desktop_filenames "$app")"
	source_entry=$(source_desktop_entry "${command[@]}")
	if [[ -f $path ]] && ! grep -qF "$MARKER desktop entry for app" "$path"; then
		source_entry=$path
	elif [[ -f $DESKTOP_BACKUP_DIR/${path##*/} ]]; then
		source_entry="$DESKTOP_BACKUP_DIR/${path##*/}"
	elif [[ -f $SYSTEM_DESKTOP_DIR/${path##*/} ]]; then
		source_entry="$SYSTEM_DESKTOP_DIR/${path##*/}"
	fi
	name=$(desktop_field "$source_entry" Name)
	icon=$(desktop_field "$source_entry" Icon)
	startup_wm_class=$(desktop_field "$source_entry" StartupWMClass)
	name=${name:-${app^}}
	icon=${icon:-application-x-executable}
	local presentation
	presentation=$(policy_query desktop-metadata "$app" "$HOME") || return 1
	name=$(jq -r --arg fallback "$name" '.name // $fallback' <<< "$presentation")
	icon=$(jq -r --arg fallback "$icon" '.icon // $fallback' <<< "$presentation")
	startup_wm_class=$(jq -r --arg fallback "$startup_wm_class" '.window_class // $fallback' <<< "$presentation")
	terminal=$(jq -r '.terminal // false' <<< "$presentation")
	local template
	template=$(jq -r '.template // empty' <<< "$presentation")
	[[ -z $template ]] || source_entry=${template//\{id\}/${path##*/}}
	name=${name% (sandboxed)}
	wrapper_name=$(config_query -r --arg app "$app" 'first(.apps[] | select(.name == $app)) | .wrapper_name // .name')
	local terminal_app_id
	terminal_app_id=$(jq -r '.terminal_app_id // empty' <<< "$presentation")
	if [[ -n $terminal_app_id ]]; then
		prefix=$(desktop_cmd /usr/bin/gnome-terminal "--app-id=$terminal_app_id" --window -- "$BIN_DIR/$wrapper_name")
		terminal=false
	else
		prefix=$(desktop_cmd "$BIN_DIR/$wrapper_name")
	fi
	preserve_desktop_entry "$path" "${command[0]}" || return 1
	if [[ -n $source_entry ]]; then
		metadata=$(jq -n --arg name "$name" --arg icon "$icon" --arg wm "$startup_wm_class" --arg terminal "$terminal" \
			'{Name: $name, Icon: $icon, StartupWMClass: $wm, Terminal: $terminal}')
		rendered=$(python3 "$SANDBOX_ROOT/lib/render_desktop.py" "$source_entry" "$prefix" "$metadata") || return 1
		install_from_stdin "$path" plain <<EOF
# $MARKER desktop entry for app "$app" — regenerate with make install
$rendered
EOF
		echo "  $path"
		return 0
	fi
	install_from_stdin "$path" plain <<EOF
# $MARKER desktop entry for app "$app" — regenerate with make install
[Desktop Entry]
Name=$name
Exec=${prefix}%U
Terminal=$terminal
Type=Application
Icon=$icon
${startup_wm_class:+StartupWMClass=$startup_wm_class}
Categories=Utility;
EOF
	echo "  $path"
}

write_desktop_override() {
	local app=$1 desktop_file=$2
	[[ $desktop_file =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*\.desktop$ ]] || return 1
	local source_entry="$SYSTEM_DESKTOP_DIR/$desktop_file"
	local path="$DESKTOP_DIR/$desktop_file" rendered
	local -a command=()
	mapfile -t command < <(app_cmd "$app")
	local presentation template metadata
	presentation=$(policy_query desktop-metadata "$app" "$HOME") || return 1
	template=$(jq -r '.template // empty' <<< "$presentation")
	[[ -z $template ]] || source_entry=${template//\{id\}/$desktop_file}
	metadata=$(jq '{Name: .name, Icon: .icon, StartupWMClass: .window_class, Terminal: (if has("terminal") then (.terminal | tostring) else null end)} | with_entries(select(.value != null))' <<< "$presentation")
    local wrapper_name prefix
    wrapper_name=$(config_query -r --arg app "$app" 'first(.apps[] | select(.name == $app)) | .wrapper_name // .name')
    local terminal_app_id
	terminal_app_id=$(jq -r '.terminal_app_id // empty' <<< "$presentation")
	if [[ -n $terminal_app_id ]]; then
		prefix=$(desktop_cmd /usr/bin/gnome-terminal "--app-id=$terminal_app_id" --window -- "$BIN_DIR/$wrapper_name")
		terminal=false
	else
		prefix=$(desktop_cmd "$BIN_DIR/$wrapper_name")
	fi
    metadata=$(jq --arg executable "$BIN_DIR/$wrapper_name" '. + {TryExec: $executable}' <<< "$metadata")
    [[ -z $terminal_app_id ]] || metadata=$(jq '. + {Terminal: "false"}' <<< "$metadata")
    # Preserve file, URI, and action arguments from the installed desktop template.
    rendered=$(python3 "$SANDBOX_ROOT/lib/render_desktop.py" "$source_entry" "$prefix" "$metadata") || return 1
	preserve_desktop_entry "$path" || return 1
	install_from_stdin "$path" plain <<EOF
# $MARKER desktop entry for app "$app" — regenerate with make install
$rendered
EOF
	echo "  $path"
}

preserve_desktop_entry() {
	local path=$1 executable=${2:-} backup="$DESKTOP_BACKUP_DIR/${1##*/}"
	[[ -e $path || -L $path ]] || return 0
	if [[ ! -L $path ]] && grep -q "$MARKER desktop entry for app" "$path"; then
		return 0
	fi
	if [[ -e $backup || -L $backup ]]; then
		# Recover PhotoCraft's known AppRun rewrite without replacing the original backup.
		if [[ ${path##*/} == ai.storyteller.photocraft.desktop &&
			$executable == "$HOME/Applications/photocraft-linux.AppImage" &&
			$(desktop_field "$path" Exec) == "$(desktop_cmd "$executable")%F" ]]; then
			return 0
		fi
		cmp -s "$path" "$backup" || {
			echo "conflicting desktop entry backup: $backup" >&2
			return 1
		}
		return 0
	fi
	mkdir -p "$DESKTOP_BACKUP_DIR"
	cp -P -- "$path" "$backup"
}

source_desktop_entry() {
	local executable=$1 executable_name entry
	shift
	if [[ $(basename "$executable") == env ]]; then
		while [[ $# -gt 0 && ( $1 == *=* || $1 == -* ) ]]; do shift; done
		[[ $# -gt 0 ]] || return 0
		executable=$1
	fi
	executable_name=$(basename "$executable")
	while IFS= read -r entry; do
		grep -qF "$MARKER desktop entry for app" "$entry" && continue
		printf '%s\n' "$entry"
		return 0
	done < <(grep -rls --include='*.desktop' -e "^Exec=.*$executable_name" \
		"$DESKTOP_DIR" "$SYSTEM_DESKTOP_DIR" 2>/dev/null)
}

desktop_field() {
	local file=$1 field=$2
	grep -s "^$field=" "$file" | head -n1 | cut -d= -f2- || true
}

# Desktop Exec has both argument quoting and desktop-string escaping.

desktop_cmd() {
	local argument
	for argument in "$@"; do
		argument=${argument//\\/\\\\}
		argument=${argument//\"/\\\"}
		argument=${argument//\$/\\\$}
		argument=${argument//\`/\\\`}
		argument=${argument//%/%%}
		argument=${argument//\\/\\\\}
		printf '"%s" ' "$argument"
	done
}
