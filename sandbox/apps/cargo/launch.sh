#!/bin/sh
set -eu
sandbox_env() {
    case ":${SANDBOX_ENV_OVERRIDES-}:" in
        *:"$1":*) ;;
        *) export "$1=$2" ;;
    esac
}
sandbox_env CARGO_HOME "${HOME}/.local/share/sandbox/cargo"
sandbox_env RUSTUP_HOME "${HOME}/.rustup"
sandbox_env RUSTUP_AUTO_INSTALL "0"
sandbox_env CARGO_REGISTRIES_CRATES_IO_PROTOCOL "sparse"
sandbox_env PATH "${HOME}/.cargo/bin:${HOME}/.local/share/sandbox/cargo/bin:/usr/local/bin:/usr/bin:/bin"
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/.cargo/bin/cargo" "$@"
fi
exec "$@"
