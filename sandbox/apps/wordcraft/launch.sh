#!/bin/sh
set -eu
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/Applications/wordcraft-linux.AppImage" "$@"
fi
exec "$@"
