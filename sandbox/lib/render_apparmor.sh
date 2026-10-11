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

app_sigrid_rules() {
	config_query -e --arg app "$1" 'any(.apps[]; .name == $app and .sigrid == true)' >/dev/null || return 0
	cat <<'EOF'
  #include <abstractions/dbus-session-strict>
  owner /run/user/*/bus rw,
  dbus (send, receive) bus=session peer=(name=org.freedesktop.secrets),
EOF
}

app_pty_rules() {
	[[ $(policy_query pty "$1") == true ]] || return 0
	cat <<'EOF'
  owner @{PROC}/@{pid}/{comm,cmdline,status,stat,cwd} r,
  owner @{PROC}/@{pid}/fd/{,**} r,
  /dev/pts/{,**} rw,
  /dev/ptmx rw,
EOF
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
  /sys/class/drm/{,**} r,
  /sys/bus/pci/{,**} r,
  /sys/dev/char/{,**} r,
  /sys/devices/pci*/{,**} r,
  /run/udev/data/+{drm,pci}:* r,
  /run/udev/data/c226:* r,
  dbus (send, receive) bus=session peer=(name=org.a11y.Bus),
  dbus (send) bus=session
       path=/org/freedesktop/portal/desktop
       interface=org.freedesktop.portal.FileChooser
       member={OpenFile,SaveFile,SaveFiles}
       peer=(name=org.freedesktop.portal.Desktop),
  dbus (send) bus=session
       path=/org/freedesktop/portal/desktop
       interface=org.freedesktop.DBus.Properties member={Get,GetAll}
       peer=(name=org.freedesktop.portal.Desktop),
  dbus (send) bus=session
       path=/org/freedesktop/portal/desktop/request/**
       interface=org.freedesktop.portal.Request member=Close
       peer=(name=org.freedesktop.portal.Desktop),
  dbus (receive) bus=session
       path=/org/freedesktop/portal/desktop/request/**
       interface=org.freedesktop.portal.Request member=Response
       peer=(name=org.freedesktop.portal.Desktop),
  /proc/ r,
  owner /run/user/*/ r,
  # Graphics loaders discover drivers through manifests outside library directories.
  /etc/{vulkan,glvnd}/{,**} r,
  /usr/share/{vulkan,glvnd}/{,**} r,
  /etc/gtk-*/** r,
  /usr/share/{themes,icons,glib-2.0}/{,**} r,
  /etc/shells r,
  /proc/sys/fs/inotify/{max_user_instances,max_user_watches} r,
EOF
}
