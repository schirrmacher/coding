#!/bin/sh
set -eu
sandbox_env() {
    case ":${SANDBOX_ENV_OVERRIDES-}:" in
        *:"$1":*) ;;
        *) export "$1=$2" ;;
    esac
}
sandbox_env VSCODE_PORTABLE "${HOME}/.local/share/sandbox/vscode"
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "/usr/bin/code" "--wait" "--no-sandbox" "--user-data-dir" "${HOME}/.local/share/sandbox/vscode/user-data" "--extensions-dir" "${HOME}/.local/share/sandbox/vscode/extensions" "$@"
fi
exec "$@"
