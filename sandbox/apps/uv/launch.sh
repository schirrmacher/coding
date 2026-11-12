#!/bin/sh
set -eu
sandbox_env() {
    case ":${SANDBOX_ENV_OVERRIDES-}:" in
        *:"$1":*) ;;
        *) export "$1=$2" ;;
    esac
}
sandbox_env UV_CACHE_DIR "${HOME}/.local/share/sandbox/uv/cache"
sandbox_env UV_PYTHON_INSTALL_DIR "${HOME}/.local/share/sandbox/uv/python"
sandbox_env UV_PYTHON_BIN_DIR "${HOME}/.local/share/sandbox/uv/python-bin"
sandbox_env UV_TOOL_DIR "${HOME}/.local/share/sandbox/uv/tools"
sandbox_env UV_TOOL_BIN_DIR "${HOME}/.local/share/sandbox/uv/bin"
sandbox_env XDG_CONFIG_HOME "${HOME}/.local/share/sandbox/uv/config"
sandbox_env XDG_DATA_HOME "${HOME}/.local/share/sandbox/uv/data"
sandbox_env UV_NO_MODIFY_PATH "1"
sandbox_env PATH "${HOME}/.local/share/sandbox/runtimes/uv:${HOME}/.local/share/sandbox/uv/bin:${HOME}/.local/share/sandbox/uv/python-bin:/usr/local/bin:/usr/bin:/bin"
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/.local/share/sandbox/runtimes/uv/uv" "$@"
fi
exec "$@"
