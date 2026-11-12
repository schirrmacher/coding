#!/bin/sh
set -eu
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    set -- "${HOME}/Applications/orca-linux.AppImage" "$@"
fi
exec "$@"
