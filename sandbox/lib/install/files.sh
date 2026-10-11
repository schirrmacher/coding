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
	if [[ $path == "$HOME/.local/bin/uv" && ! -L $path &&
		$executable == "$HOME/.local/share/sandbox/runtimes/uv/uv" &&
		-f $backup && ! -L $backup ]] && cmp -s "$path" "$backup" && cmp -s "$path" "$executable"; then
		return 0
	fi
	if [[ ! -L $path || $(realpath "$path") != $(realpath "$executable") ]]; then
		echo "refusing to replace unmanaged launcher: $path" >&2
		return 1
	fi
	if [[ ! -e $backup && ! -L $backup ]]; then
		mkdir -p "$BACKUP_DIR"
		cp -P -- "$path" "$backup"
		return
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
