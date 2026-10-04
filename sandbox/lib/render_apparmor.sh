# Render per-app AppArmor grants from the shared configuration queries.

app_file_rules() {
	local app=$1 fallback=$2 directory config_path
	local paths
	paths=$(config_paths) || return 1
	while IFS= read -r config_path; do
		printf '  "%s" r,\n  deny "%s" wkl,\n' "$config_path" "$config_path"
	done <<< "$paths"
	while IFS= read -r directory; do
		printf '  "%s/" r,\n  "%s/**" rwklmix,\n' "$directory" "$directory"
		# Nested bwrap creates directory mountpoints beneath its staged root.
		printf '  "/newroot%s/" rw,\n  "/newroot%s/**/" rw,\n' "$directory" "$directory"
	done < <(app_writable_directories "$app" "$fallback")
	while IFS= read -r directory; do
		# Rustup takes a shared lock even when it only reads settings.
		printf '  "%s/" r,\n  "%s/**" rmk,\n  deny "%s/**" wl,\n' "$directory" "$directory" "$directory"
	done < <(app_readable_directories "$app")
	while IFS= read -r directory; do
		printf '  deny "%s/" r,\n  deny "%s/**" rwklmx,\n' "$directory" "$directory"
	done < <(app_private_directories "$app")
}

app_gui_rules() {
	local gui
	gui=$(config_query -r --arg app "$1" 'first(.apps[] | select(.name == $app)).gui // false')
	[[ $gui == true ]] || return 0
	cat <<'EOF'
  #include <abstractions/X>
  #include <abstractions/fonts>
  #include <abstractions/wayland>
  #include <abstractions/dbus-session-strict>
  # bwrap creates this mountpoint before switching to its new root.
  /newroot/tmp/.X11-unix/ rw,
  /dev/ r,
  /proc/ r,
  owner /run/user/*/ r,
  /etc/gtk-*/** r,
  /usr/share/{themes,icons,glib-2.0}/{,**} r,
  /etc/shells r,
  /proc/sys/fs/inotify/{max_user_instances,max_user_watches} r,
EOF
}
