# Source-only lifecycle for sandbox-owned localhost relays.
LOCALHOST_UNIT_DIR=/etc/systemd/system
SOCKET_PROXY=/usr/lib/systemd/systemd-socket-proxyd

require_localhost_commands() {
    config_query -e 'any(.apps[]; (.localhost_ports // [] | length) > 0)' >/dev/null || return 0
    [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null \
        || { echo 'localhost-ports requires systemd' >&2; return 1; }
    [[ -x $SOCKET_PROXY ]] || { echo "missing prerequisite: $SOCKET_PROXY" >&2; return 1; }
    [[ ${SUDO_UID:-0} != 0 ]] || { echo 'localhost relays require a non-root invoking user' >&2; return 1; }
}

localhost_units() {
    local path
    for path in "$LOCALHOST_UNIT_DIR"/sandbox-localhost-*.service "$LOCALHOST_UNIT_DIR"/sandbox-localhost-*.socket; do
        [[ ! -f $path ]] || printf '%s\n' "${path##*/}"
    done
}

stop_localhost_services() {
    local -a units=()
    mapfile -t units < <(localhost_units)
    [[ ${#units[@]} == 0 ]] || systemctl stop "${units[@]}"
}

start_localhost_services() {
    local -a units=()
    local unit
    while read -r unit; do
        # Host services are socket-activated; namespaces must bind before setup succeeds.
        [[ $unit == sandbox-localhost-host-*.service ]] || units+=("$unit")
    done < <(localhost_units)
    [[ ${#units[@]} == 0 ]] || systemctl start "${units[@]}"
}

remove_localhost_services() {
    local -a units=()
    mapfile -t units < <(localhost_units)
    [[ ${#units[@]} != 0 ]] || return 0
    stop_localhost_services || return 1
    local unit
    for unit in "${units[@]}"; do
        rm -f -- "$LOCALHOST_UNIT_DIR/$unit" || return 1
    done
    systemctl daemon-reload
}

install_localhost_services() {
    remove_localhost_services || return 1
    config_query -e 'any(.apps[]; (.localhost_ports // [] | length) > 0)' >/dev/null || return 0
    cp "$SCRIPT_DIR/src/localhost_relay.py" "$PROXY_DIR/" || return 1
    python3 "$SCRIPT_DIR/src/localhost_services.py" --uid "$SUDO_UID" \
        --output "$LOCALHOST_UNIT_DIR" <<< "$CONFIG_JSON" >/dev/null || return 1
    systemctl daemon-reload || return 1
    start_localhost_services || { stop_localhost_services; return 1; }
}
