#!/bin/sh
set -eu
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/Applications/designcraft-linux.AppImage" "$@"
fi
exec "$@"
