# Render standalone AppArmor profiles from native app rules and shared protections.
APPARMOR_RULES=$(cd "$(dirname "${BASH_SOURCE[0]}")/../rules/apparmor" && pwd)

app_file_rules() {
	local app=$1 config_path paths
	printf '  # Definition sources are readable and cannot be modified.\n'
	paths=$(config_paths) || return 1
	while IFS= read -r config_path; do
		printf '  "%s" r,\n  deny "%s" wkl,\n' "$config_path" "$config_path"
	    printf '\n'
	done <<< "$paths"
	paths=$(config_query -r '.config_directories[]') || return 1
	while IFS= read -r config_path; do
		printf '  "%s/" r,\n  "%s/**" r,\n  deny "%s/{,**}" wkl,\n' "$config_path" "$config_path" "$config_path"
	done <<< "$paths"
	printf '\n  # Application grants.\n'
	policy_query apparmor "$app" || return 1
	printf '\n  # Other applications keep their private state.\n'
	paths=$(app_private_directories "$app") || return 1
	while IFS= read -r config_path; do
		[[ -n $config_path ]] || continue
		printf '  deny "%s/" r,\n  deny "%s/**" rwklmx,\n' "$config_path" "$config_path"
	done <<< "$paths"
}

render_apparmor() {
	local app=$1 line
	while IFS= read -r line; do
		case $line in
		@BASE_RULES@) cat "$APPARMOR_RULES/base" || return 1 ;;
		@SECRET_RULES@) python3 "${APPARMOR_RULES%/rules/apparmor}/src/render_secret_rules.py" apparmor || return 1 ;;
		@DIRECTORY_RULES@) app_file_rules "$app" || return 1 ;;
		*) printf '%s\n' "${line//@SANDBOX_APP@/$app}" ;;
		esac
	done < "$APPARMOR_RULES/profile"
}
