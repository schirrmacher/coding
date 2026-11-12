#!/bin/sh
set -eu
if [ "${1-}" = --sandbox-command ]; then
    shift
else
    # The isolated profile also prevents reuse of an unsandboxed browser process.
    set -- /usr/bin/brave-browser --user-data-dir="$HOME/.local/share/sandbox/brave" "$@"
fi
exec "$@"
