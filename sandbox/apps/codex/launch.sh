#!/bin/sh
set -eu
sandbox_env() {
    case ":${SANDBOX_ENV_OVERRIDES-}:" in
        *:"$1":*) ;;
        *) export "$1=$2" ;;
    esac
}
sandbox_env CODEX_HOME "${HOME}/.codex"
sandbox_env GH_CONFIG_DIR "${HOME}/.local/share/sandbox/gh"
sandbox_env GH_NO_UPDATE_NOTIFIER "1"
sandbox_env CARGO_HOME "${HOME}/.local/share/sandbox/cargo"
sandbox_env RUSTUP_HOME "${HOME}/.rustup"
sandbox_env RUSTUP_AUTO_INSTALL "0"
sandbox_env CARGO_REGISTRIES_CRATES_IO_PROTOCOL "sparse"
sandbox_env UV_CACHE_DIR "${HOME}/.local/share/sandbox/uv/cache"
sandbox_env UV_PYTHON_INSTALL_DIR "${HOME}/.local/share/sandbox/uv/python"
sandbox_env UV_PYTHON_BIN_DIR "${HOME}/.local/share/sandbox/uv/python-bin"
sandbox_env UV_TOOL_DIR "${HOME}/.local/share/sandbox/uv/tools"
sandbox_env UV_TOOL_BIN_DIR "${HOME}/.local/share/sandbox/uv/bin"
sandbox_env UV_NO_MODIFY_PATH "1"
sandbox_env PATH "${HOME}/.cargo/bin:${HOME}/.local/share/sandbox/cargo/bin:${HOME}/.local/share/sandbox/runtimes/uv:${HOME}/.local/share/sandbox/uv/bin:${HOME}/.local/share/sandbox/uv/python-bin:${HOME}/.local/share/sandbox/runtimes/sigrid:/usr/local/bin:/usr/bin:/bin"
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/.local/share/codex/current/bin/codex" "$@"
fi
exec "$@"
