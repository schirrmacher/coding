#!/bin/sh
set -eu
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/Applications/gridcraft-linux.AppImage" "$@"
fi
exec "$@"
