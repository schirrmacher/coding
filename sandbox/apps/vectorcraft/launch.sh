#!/bin/sh
set -eu
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/Applications/vectorcraft-linux.AppImage" "$@"
fi
exec "$@"
