#!/bin/sh
set -eu
sandbox_env() {
    case ":${SANDBOX_ENV_OVERRIDES-}:" in
        *:"$1":*) ;;
        *) export "$1=$2" ;;
    esac
}
sandbox_env PHOTOCRAFT_NO_DESKTOP_INTEGRATION "1"
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/Applications/photocraft-linux.AppImage" "$@"
fi
exec "$@"
