# Source-only files operations.

remove_stale() {
	local directory=$1 suffix=$2
	local file filename managed_file
	for file in "$directory"/*"$suffix"; do
		[[ -f $file ]] || continue
		grep -q "$MARKER" "$file" 2>/dev/null || continue
		filename=$(basename "$file")
		for managed_file in "${MANAGED_FILES[@]}"; do
			[[ $filename == "$managed_file" ]] && continue 2
		done
		rm -f "$file"
		echo "  removed stale $file"
	done
}

preserve_launcher() {
	local path=$1 executable=$2 backup="$BACKUP_DIR/${1##*/}"
	[[ -e $path || -L $path ]] || return 0
	if [[ ! -L $path ]] && grep -q "$MARKER wrapper for app" "$path"; then
		return 0
	fi
	if [[ ! -L $path || ( -n $executable && $(realpath "$path") != $(realpath "$executable") ) ]]; then
		echo "refusing to replace unmanaged launcher: $path" >&2
		return 1
	fi
	if [[ ! -e $backup && ! -L $backup ]]; then
		mkdir -p "$BACKUP_DIR"
		cp -P -- "$path" "$backup"
		return
	fi
	if [[ -f $backup && ! -L $backup ]] && cmp -s "$path" "$backup"; then
        return 0
    fi
	if [[ ! -L $backup || $(readlink "$backup") != $(readlink "$path") ]]; then
		echo "conflicting launcher backup: $backup" >&2
		return 1
	fi
	return 0
}

install_from_stdin() {
	local path=$1 mode=$2 temporary_file="$1.tmp"
	cat > "$temporary_file"
	[[ $mode == executable ]] && chmod +x "$temporary_file"
	mv "$temporary_file" "$path"
}

quoted_cmd() {
	printf '%q ' "$@"
}

# Install native desktop entries, retaining originals for rollback.
write_desktop_entry() {
	local app=$1 desktop_file files
	files=$(desktop_filenames "$app") || return 1
	while IFS= read -r desktop_file; do
		[[ -n $desktop_file ]] || continue
		write_desktop_override "$app" "$desktop_file" || return 1
	done <<< "$files"
}

write_desktop_override() {
	[[ ${CONFIG_SOURCE:-} == "$CONFIG" ]] || read_config || return 1
	local app=$1 desktop_file=$2 wrapper prefix rendered path
	wrapper=$(config_query -r --arg app "$app" 'first(.apps[] | select(.name == $app)).wrappers[0] // empty') || return 1
	[[ -n $wrapper ]] || { echo "desktop app has no command wrapper: $app" >&2; return 1; }
	prefix=$(desktop_cmd "$BIN_DIR/$wrapper")
	rendered=$(python3 "$SANDBOX_ROOT/lib/render_desktop.py" --native "$app" "$desktop_file" "$prefix" "$BIN_DIR/$wrapper" <<< "$CONFIG_JSON") || return 1
	path="$DESKTOP_DIR/$desktop_file"
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
		cmp -s "$path" "$backup" || {
			echo "conflicting desktop entry backup: $backup" >&2
			return 1
		}
		return 0
	fi
	mkdir -p "$DESKTOP_BACKUP_DIR"
	cp -P -- "$path" "$backup"
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

# Install shared desktop integration; application setup is separate.
prepare_installation() {
    mkdir -p "$BIN_DIR" "$DESKTOP_DIR"
    local browser="$HOME/.local/share/sandbox/runtimes/browser/xdg-open"
    mkdir -p "${browser%/*}"
    install -m 0755 "$SANDBOX_ROOT/bin/open_browser" "$browser"
}
