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
sandbox_env PATH "${HOME}/.local/share/sandbox/runtimes/sigrid:/usr/local/bin:/usr/bin:/bin"
sandbox_env OPENCODE_DISABLE_AUTOUPDATE "1"
sandbox_env OPENCODE_DISABLE_MODELS_FETCH "1"
sandbox_env OPENCODE_DISABLE_CLAUDE_CODE_SKILLS "1"
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/.opencode/bin/opencode" "$@"
fi
exec "$@"
