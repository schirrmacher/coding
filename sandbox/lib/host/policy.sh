# Source-only policy operations.

install_apparmor() {
	if [[ ! -d /sys/kernel/security/apparmor ]] || ! command -v apparmor_parser >/dev/null; then
		echo "WARNING: AppArmor not available; file rules will not be enforced" >&2
		return
	fi

	local app rules gui_rules profile_path staging
	staging=$(mktemp -d) || return 1
	for app in "${APPS[@]}"; do
		rules=$(app_file_rules "$app" "$DEFAULT_PROJECT_DIRECTORY" && app_sigrid_rules "$app" && app_browser_rules "$app")
		gui_rules=$(app_gui_rules "$app")
		gui_rules+=$'\n'$(app_pty_rules "$app")
		profile_path="$staging/sandbox-$app"
		awk -v app="$app" -v rules="$rules" -v gui_rules="$gui_rules" '
			$0 == "@DIRECTORY_RULES@" { print rules; next }
			$0 == "@GUI_RULES@" { print gui_rules; next }
			{
				if ($0 !~ /^[ \t]*#/) gsub(/@SANDBOX_APP@/, app)
				print
			}' \
			"$SCRIPT_DIR/../apparmor/sandbox_template" > "$profile_path"
		if ! apparmor_parser -Q -T "$profile_path"; then
			rm -rf "$staging"
			return 1
		fi
	done
	for app in "${APPS[@]}"; do
		profile_path="/etc/apparmor.d/sandbox-$app"
		install -m 644 "$staging/sandbox-$app" "$profile_path" || { rm -rf "$staging"; return 1; }
		apparmor_parser -r "$profile_path" || { rm -rf "$staging"; return 1; }
	done
	rm -rf "$staging"
	echo "==> apparmor: ${#APPS[@]} profiles loaded"
}
