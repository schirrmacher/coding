#!/usr/bin/env bash
# Check locally by default; --installed verifies host setup without changing it.
set -euo pipefail

SANDBOX_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CONFIG="$SANDBOX_ROOT/sandbox.toml"
source "$SANDBOX_ROOT/lib/query_config.sh"
LAUNCHER="$SANDBOX_ROOT/bin/sandbox"
PROXY_CONFIG=/usr/local/lib/sandbox/apps.json
FIXTURE=
TEST_FILES=()

main() {
	local installed=0 result=0 code app
	APPS=()
	while [[ $# -gt 0 ]]; do
		case $1 in
		--help)
			usage
			return 0
			;;
		--installed)
			installed=1
			shift
			;;
		--app)
			[[ $# -ge 2 && $2 =~ ^[a-z][a-z0-9-]*$ ]] || {
				usage >&2
				return 2
			}
			APPS+=("$2")
			shift 2
			;;
		*)
			usage >&2
			return 2
			;;
		esac
	done
	[[ $installed == 1 || ${#APPS[@]} == 0 ]] || {
		usage >&2
		return 2
	}

	require_commands python3 jq || return 2
	read_config || return 2
	if [[ $installed == 1 ]]; then
		config_query -e '.apps | type == "array" and length > 0' >/dev/null || return 2
		if [[ ${#APPS[@]} == 0 ]]; then
			mapfile -t APPS < <(config_query -r '.apps[].name')
		fi
		for app in "${APPS[@]}"; do
			config_query -e --arg app "$app" 'any(.apps[]; .name == $app)' >/dev/null || {
				echo "ERROR unknown app: $app" >&2
				return 2
			}
		done
	fi
	local_checks || result=1
	if [[ $installed == 1 ]]; then
		installed_checks || {
			code=$?
			[[ $code == 2 ]] && return 2
			result=1
		}
	fi

	if [[ $result == 0 ]]; then
		echo "PASS sandbox checks"
	else
		echo "FAIL sandbox checks"
	fi
	return "$result"
}

local_checks() {
	local failed=0 script
	for script in "$SANDBOX_ROOT"/bin/* "$SANDBOX_ROOT"/host/* "$SANDBOX_ROOT"/lib/*.sh \
		"$SANDBOX_ROOT"/tests/*.sh "$SANDBOX_ROOT"/tests/boundary/*.sh; do
		if bash -n "$script"; then
			printf 'PASS syntax: %s\n' "${script#"$SANDBOX_ROOT"/}"
		else
			failed=1
		fi
	done
	if python3 -m unittest discover -s "$SANDBOX_ROOT/tests" -v; then
		echo "PASS regressions"
	else
		failed=1
	fi
	return "$failed"
}

installed_checks() {
	local app status failed=0
	[[ $EUID -ne 0 ]] || {
		echo "ERROR run installed checks as your normal user" >&2
		return 2
	}
	[[ -r $PROXY_CONFIG ]] || {
		echo "ERROR missing proxy config: $PROXY_CONFIG" >&2
		return 2
	}
	require_commands sudo ip nft aa-exec bwrap setpriv getent realpath mktemp timeout id tar || return 2
	status=$(SANDBOX_ALLOW_NO_APPARMOR=0 sudo -n "$LAUNCHER" status) || {
		echo "ERROR cannot inspect sandbox; prepare setup and sudo access first" >&2
		return 2
	}
	if ! [[ $status == *'nftables: filtered'* ]]; then
		echo "FAIL nftables: sandbox table missing"
		failed=1
	fi
	FIXTURE=$(mktemp -d /var/tmp/sandbox-test.XXXXXX) || return 2
	trap cleanup EXIT
	trap 'exit 130' INT
	trap 'exit 143' TERM
	printf 'host fixture\n' > "$FIXTURE/control" || return 2
	for app in "${APPS[@]}"; do
		echo "==> app $app"
		if verify_app "$app"; then
			echo "PASS app $app"
		else
			echo "FAIL app $app"
			failed=1
		fi
	done
	return "$failed"
}

verify_app() {
	local app=$1 directories endpoints directory readable private codex_home
	directories=$(app_writable_directories "$app" "$PWD" | jq -Rsc 'split("\n") | map(select(length > 0))')
	readable=$(app_readable_directories "$app" | jq -Rsc 'split("\n") | map(select(length > 0))')
	private=$(app_private_directories "$app" | jq -Rsc 'split("\n") | map(select(length > 0))')
	codex_home=$(app_codex_home "$app")
	[[ -z $codex_home ]] || codex_home=$(realpath "$codex_home")
	endpoints=$(config_query -c --arg app "$app" 'first(.apps[] | select(.name == $app)).endpoints')
	if ! jq -e --arg app "$app" --argjson endpoints "$endpoints" '
		any(.apps[]; .name == $app and
			(.endpoints | map(ascii_downcase | rtrimstr(".")) | sort) ==
			($endpoints | map(ascii_downcase | rtrimstr(".")) | sort))' "$PROXY_CONFIG" >/dev/null; then
		echo "FAIL app $app: missing or stale proxy endpoints"
		return 1
	fi
	while IFS= read -r directory; do
		if [[ -e $directory/.sandbox-test-${FIXTURE##*/} || -L $directory/.sandbox-test-${FIXTURE##*/} ]]; then
			echo "FAIL app $app: test filename already exists" >&2
			return 1
		fi
		TEST_FILES+=("$directory/.sandbox-test-${FIXTURE##*/}")
	done < <(jq -r '.[]' <<< "$directories"; jq -r '.[]' <<< "$readable")
	# Send probes through stdin: app profiles need not grant reads to this repo.
	tar -C "$SANDBOX_ROOT/tests/boundary" -cf - test_boundary.sh boundary_probe.py | \
	SANDBOX_ALLOW_NO_APPARMOR=0 SANDBOX_TEST_UNPASSED=host-only \
		sudo -n "$LAUNCHER" --app "$app" \
		--env "SANDBOX_TEST_CONFIG=$(canonical_config_path)" \
		--env "SANDBOX_TEST_CONFIGS=$(config_query -c '.config_paths')" \
		--env "SANDBOX_TEST_UID=$(id -u)" \
		--env "SANDBOX_TEST_DIRECTORIES=$directories" \
		--env "SANDBOX_TEST_ENDPOINTS=$endpoints" \
		--env "SANDBOX_TEST_READABLE=$readable" \
		--env "SANDBOX_TEST_PRIVATE=$private" \
		--env "SANDBOX_TEST_CODEX_HOME=$codex_home" \
		--env "SANDBOX_TEST_FIXTURE=$FIXTURE" \
		--env 'SANDBOX_TEST_PASSED=two words=a=b' \
		bash -c '
			set -euo pipefail
			scratch=$(mktemp -d)
			cleanup_scratch() {
				rm -rf -- "$scratch"
			}
			trap cleanup_scratch EXIT
			tar -xf - -C "$scratch"
			bash "$scratch/test_boundary.sh"
		'
}

cleanup() {
	local file
	for file in "${TEST_FILES[@]}"; do
		rm -f -- "$file"
	done
	[[ -z $FIXTURE ]] || rm -rf -- "$FIXTURE"
}

require_commands() {
	local command
	for command in "$@"; do
		command -v "$command" >/dev/null && continue
		echo "ERROR missing prerequisite: $command" >&2
		return 2
	done
}

usage() {
	cat <<'EOF'
Usage: test_sandbox.sh [--installed [--app NAME]...] [--help]

Default: Bash syntax and Python regressions; no sudo or network access.
--installed: also check each configured app on an already prepared Linux host.
--app NAME: select an app (repeatable; requires --installed).

Run as your normal user. Installed checks require passwordless sudo for the
launcher (or a cached sudo session), AppArmor, namespaces, nftables, and the proxy.
They create temporary test files, but never install, start, or remove host setup.
Exit: 0 success; 1 failed checks; 2 invalid usage or missing prerequisites.
EOF
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
	main "$@"
fi
