# Source-only execution operations.

run_payload() {
	[[ ${#CMD[@]} -gt 0 ]] || CMD=(bash)

	prepare_directories
	prepare_network
	prepare_mounts_and_environment
	prepare_apparmor

	build_launch_command
	exec "${LAUNCH_COMMAND[@]}"
}

build_launch_command() {
	local plan
	plan=$(python3 "$SANDBOX_ROOT/lib/plan_launch.py" \
		"$NS" "$SUDO_UID" "$SUDO_GID" "$WORKING_DIRECTORY" "$HOME_DIR" \
		"${TERM:-dumb}" "${LANG:-C.UTF-8}" "$APP" "${DIRECTORIES[*]}" "$PROXY_HOST" "$PROXY_PORT" \
		apparmor "${#AA_EXEC[@]}" "${AA_EXEC[@]}" \
		ipc "${#IPC_ARGS[@]}" "${IPC_ARGS[@]}" \
		network "${#NETWORK_ARGS[@]}" "${NETWORK_ARGS[@]}" \
		write "${#BIND_ARGS[@]}" "${BIND_ARGS[@]}" \
		read "${#READ_ARGS[@]}" "${READ_ARGS[@]}" \
		mask "${#MASK_ARGS[@]}" "${MASK_ARGS[@]}" \
		gui "${#GUI_ARGS[@]}" "${GUI_ARGS[@]}" \
		config "${#CONFIG_ARGS[@]}" "${CONFIG_ARGS[@]}" \
		environment "${#APP_ENV_ARGS[@]}" "${APP_ENV_ARGS[@]}" \
		overrides "${#ENV_ARGS[@]}" "${ENV_ARGS[@]}" \
		payload "${#CMD[@]}" "${CMD[@]}") || return 1
	mapfile -d '' -t LAUNCH_COMMAND < <(jq -j '.[] + "\u0000"' <<< "$plan")
}

prepare_network() {
	NS="sandbox-$APP"
	PROFILE="sandbox-$APP"
	ip netns list | grep -q "^$NS " || {
		echo "network namespace $NS missing; add app '$APP' to sandbox/sandbox.toml and run:" >&2
		echo "  sudo sandbox up" >&2
		exit 1
	}

	[[ -r $PROXY_CONFIG ]] || {
		echo "proxy config missing: $PROXY_CONFIG; run: sudo sandbox up" >&2
		exit 1
	}
	local fingerprint
	fingerprint=$(config_query -r '.policy_fingerprint') || exit 1
	jq -e --arg fingerprint "$fingerprint" '.policy_fingerprint == $fingerprint' "$PROXY_CONFIG" >/dev/null || {
		echo "installed policy is stale; run: sudo sandbox up" >&2
		exit 1
	}
	PROXY_HOST=$(resolve_proxy_host "$APP")
	[[ -n $PROXY_HOST ]] || {
		echo "app '$APP' not in $PROXY_CONFIG; run: sudo sandbox up" >&2
		exit 1
	}
	PROXY_PORT=$(jq -r '.proxy.sni_port' "$PROXY_CONFIG")
}

prepare_apparmor() {
	# Fail closed unless the caller explicitly waives AppArmor.
	if aa-exec -p "$PROFILE" true 2>/dev/null; then
		AA_EXEC=(aa-exec -p "$PROFILE" --)
	elif [[ ${SANDBOX_ALLOW_NO_APPARMOR:-0} == 1 ]]; then
		echo "WARNING: proceeding without the AppArmor profile (SANDBOX_ALLOW_NO_APPARMOR=1)" >&2
		AA_EXEC=()
	else
		echo "AppArmor profile '$PROFILE' not loaded; run: sudo sandbox up" >&2
		echo "set SANDBOX_ALLOW_NO_APPARMOR=1 to proceed without file rules (not recommended)" >&2
		exit 1
	fi
}

resolve_proxy_host() {
	local app=$1
	jq -r --arg app "$app" 'first(.apps[] | select(.name == $app) | .ip)' "$PROXY_CONFIG" 2>/dev/null || true
}

# Mask only existing directories; creating a mountpoint on the read-only root fails.
