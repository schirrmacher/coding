#!/bin/sh
set -eu
sandbox_env() {
    case ":${SANDBOX_ENV_OVERRIDES-}:" in
        *:"$1":*) ;;
        *) export "$1=$2" ;;
    esac
}
sandbox_env BROWSER "${HOME}/.local/share/sandbox/runtimes/browser/xdg-open"
sandbox_env VIBE_HOME "${HOME}/.vibe"
sandbox_env GH_CONFIG_DIR "${HOME}/.local/share/sandbox/gh"
sandbox_env GH_NO_UPDATE_NOTIFIER "1"
sandbox_env PATH "${HOME}/.local/share/sandbox/runtimes/browser:${HOME}/.local/share/sandbox/runtimes/sigrid:/usr/local/bin:/usr/bin:/bin"
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/.local/share/mistral-vibe/bin/vibe" "$@"
fi
exec "$@"
