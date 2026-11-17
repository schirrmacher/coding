# Docker can set FORWARD to DROP before the sandbox's nftables chain runs.
# These exceptions still pass through the sandbox's private-address and port filters.

remove_host_forwarding_jump() {
    local status
    while true; do
        if iptables -w -C FORWARD -j SANDBOX-WEB 2>/dev/null; then
            iptables -w -D FORWARD -j SANDBOX-WEB || return 1
        else
            status=$?
            [[ $status == 1 ]] && return 0
            echo "cannot inspect sandbox forwarding jump" >&2
            return "$status"
        fi
    done
}

remove_host_forwarding() {
    command -v iptables >/dev/null || return 0
    local rules
    rules=$(iptables -w -S) || return 1
    grep -qx -- '-N SANDBOX-WEB' <<< "$rules" || return 0
    remove_host_forwarding_jump || return 1
    iptables -w -F SANDBOX-WEB || return 1
    iptables -w -X SANDBOX-WEB
}

install_host_forwarding() {
    if ! config_query -e 'any(.apps[]; .network == "web")' >/dev/null; then
        remove_host_forwarding
        return
    fi

    local rules app address index=0
    rules=$(iptables -w -S) || return 1
    if ! grep -qx -- '-N SANDBOX-WEB' <<< "$rules"; then
        iptables -w -N SANDBOX-WEB || return 1
    fi
    iptables -w -F SANDBOX-WEB || return 1
    for app in "${APPS[@]}"; do
        if config_query -e --arg app "$app" 'any(.apps[]; .name == $app and .network == "web")' >/dev/null; then
            address=$(pool_ns_ip "$index") || return 1
            iptables -w -A SANDBOX-WEB -i "sbh$index" -s "$address/32" \
                -p tcp -m multiport --dports 80,443 -j ACCEPT || return 1
            iptables -w -A SANDBOX-WEB -o "sbh$index" -d "$address/32" \
                -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT || return 1
        fi
        index=$((index + 1))
    done
    # Reinsert before Docker even if another firewall moved an existing jump.
    remove_host_forwarding_jump || return 1
    iptables -w -I FORWARD 1 -j SANDBOX-WEB
}
