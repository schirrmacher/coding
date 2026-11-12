# Source-only policy operations.

install_apparmor() {
	if [[ ! -d /sys/kernel/security/apparmor ]] || ! command -v apparmor_parser >/dev/null; then
		echo "WARNING: AppArmor not available; file rules will not be enforced" >&2
		return
	fi

	local app profile_path staging
	staging=$(mktemp -d) || return 1
	for app in "${APPS[@]}"; do
		profile_path="$staging/sandbox-$app"
		if ! render_apparmor "$app" "$DEFAULT_PROJECT_DIRECTORY" > "$profile_path"; then
			rm -rf "$staging"
			return 1
		fi
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
