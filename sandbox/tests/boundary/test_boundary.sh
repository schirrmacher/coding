#!/usr/bin/env bash
# Run inside the sandbox; test_sandbox.sh --installed supplies host controls.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROBE="$SCRIPT_DIR/boundary_probe.py"
PROXY_CONFIG=/usr/local/lib/sandbox/apps.json
PASS=0
FAIL=0

main() {
	local app=${SANDBOX_APP:?run via the sandbox launcher}
	local proxy_host=${SANDBOX_PROXY_HOST:?}
	local proxy_port=${SANDBOX_PROXY_PORT:?}
	local endpoint directory blocked=blocked.sandbox-test.invalid
	local -a endpoints directories

	command -v python3 >/dev/null && command -v jq >/dev/null && command -v timeout >/dev/null || {
		echo "ERROR python3, jq, and timeout are required" >&2
		return 2
	}
	if [[ -n ${SANDBOX_TEST_ENDPOINTS:-} ]]; then
		mapfile -t endpoints < <(jq -r '.[]' <<< "$SANDBOX_TEST_ENDPOINTS")
	else
		[[ -r $PROXY_CONFIG ]] || {
			echo "ERROR proxy config missing; use test_sandbox.sh --installed" >&2
			return 2
		}
		mapfile -t endpoints < <(jq -r --arg app "$app" \
			'.apps[] | select(.name == $app) | .endpoints[]' "$PROXY_CONFIG")
	fi
	[[ ${#endpoints[@]} -gt 0 ]] || {
		echo "ERROR no endpoints for $app" >&2
		return 2
	}

	if [[ -n ${SANDBOX_TEST_DIRECTORIES:-} ]]; then
		mapfile -t directories < <(jq -r '.[]' <<< "$SANDBOX_TEST_DIRECTORIES")
	else
		directories=("${SANDBOX_DIRECTORY:?}")
	fi

	while printf '%s\n' "${endpoints[@]}" | jq -Rse --arg blocked "$blocked" \
		'split("\n") | any(.[]; ascii_downcase == $blocked)' >/dev/null; do
		blocked="extra.$blocked"
	done

	echo "==> boundary: $app"
	check "identity, capabilities, AppArmor, and environment" python3 "$PROBE" confinement
	check "secret directories hidden or denied" python3 "$PROBE" secrets
	check "host fixture is read-only" python3 "$PROBE" readonly
	if [[ -n ${SANDBOX_TEST_CONFIGS:-} ]]; then
		while IFS= read -r directory; do
			check "configuration is read-only: $directory" python3 "$PROBE" readonly-config "$directory"
		done < <(jq -r '.[]' <<< "$SANDBOX_TEST_CONFIGS")
	elif [[ -n ${SANDBOX_TEST_CONFIG:-} ]]; then
		check "sandbox configuration is read-only" python3 "$PROBE" readonly-config "$SANDBOX_TEST_CONFIG"
	fi
	for directory in "${directories[@]}"; do
		check "writable: $directory" python3 "$PROBE" writable "$directory"
	done

	while IFS= read -r directory; do
		check "read-only shared directory: $directory" python3 "$PROBE" readonly-directory "$directory"
	done < <(jq -r '.[]' <<< "${SANDBOX_TEST_READABLE:-[]}")
	if [[ $app == cargo ]]; then
		check "rustup settings readable with a shared lock" python3 "$PROBE" locked-read "$HOME/.rustup/settings.toml"
	fi
	while IFS= read -r directory; do
		check "other app state denied: $directory" python3 "$PROBE" private-directory "$directory"
	done < <(jq -r '.[]' <<< "${SANDBOX_TEST_PRIVATE:-[]}")

	# Positive controls prevent an offline proxy from passing all denial checks.
	for endpoint in "${endpoints[@]}"; do
		check "DNS: $endpoint" python3 "$PROBE" dns "$endpoint"
		check "allowed TLS: $endpoint" python3 "$PROBE" tls-allow "$endpoint"
	done
	check "denied SNI" python3 "$PROBE" tls-deny "$proxy_host" "$blocked"
	check "TLS without SNI" python3 "$PROBE" tls-deny "$proxy_host" ''
	check "direct IP TLS without SNI" python3 "$PROBE" tls-deny 1.1.1.1 ''
	check "plain HTTP rejected" python3 "$PROBE" http-deny "$proxy_host" "$proxy_port"
	check "direct TCP DNS denied" python3 "$PROBE" tcp-deny 8.8.8.8 53
	check "host port 22 denied" python3 "$PROBE" tcp-deny "$proxy_host" 22
	printf '%d passed, %d failed\n' "$PASS" "$FAIL"
	[[ $FAIL == 0 ]]
}

check() {
	local label=$1
	shift
	if timeout --kill-after=2 20 "$@"; then
		printf 'PASS %s\n' "$label"
		PASS=$((PASS + 1))
	else
		printf 'FAIL %s\n' "$label"
		FAIL=$((FAIL + 1))
	fi
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
	main "$@"
fi
