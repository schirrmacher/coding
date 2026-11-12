#!/bin/sh
set -eu
sandbox_env() {
    case ":${SANDBOX_ENV_OVERRIDES-}:" in
        *:"$1":*) ;;
        *) export "$1=$2" ;;
    esac
}
sandbox_env GH_CONFIG_DIR "${HOME}/.local/share/sandbox/gh"
sandbox_env GH_NO_UPDATE_NOTIFIER "1"
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "/usr/bin/gh" "$@"
fi
exec "$@"
