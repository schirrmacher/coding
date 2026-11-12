#!/bin/sh
set -eu
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/.local/zed.app/bin/zed" "--foreground" "$@"
fi
exec "$@"
