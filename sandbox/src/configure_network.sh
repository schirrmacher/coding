NETWORK_RULES=$(cd "$(dirname "${BASH_SOURCE[0]}")/../rules" && pwd)
source "$(dirname "${BASH_SOURCE[0]}")/host_forwarding.sh"

# Source-only network operations.

create_app_network() {
	local app=$1 index=$2
	local namespace="sandbox-$app"
	local host_veth="sbh$index" namespace_veth="sbe$index"
	local host_ip namespace_ip
	host_ip=$(pool_host_ip "$index")
	namespace_ip=$(pool_ns_ip "$index")

	if ! ip netns list | grep -q "^$namespace "; then
		ip netns add "$namespace"
	fi

	# Recreate veths so reruns pick up configuration changes.
	ip link del "$host_veth" 2>/dev/null || true
	ip link add "$host_veth" type veth peer name "$namespace_veth"
	ip link set "$namespace_veth" netns "$namespace"

	ip addr add "$host_ip/30" dev "$host_veth"
	ip link set "$host_veth" up

	ip netns exec "$namespace" sysctl -q -w net.ipv6.conf.all.disable_ipv6=1
	ip netns exec "$namespace" ip link set lo up
	ip netns exec "$namespace" ip addr add "$namespace_ip/30" dev "$namespace_veth"
	ip netns exec "$namespace" ip link set "$namespace_veth" up
	ip netns exec "$namespace" ip route replace default via "$host_ip"

	# ip netns exec binds this resolver over /etc/resolv.conf.
	mkdir -p "/etc/netns/$namespace"
	printf 'nameserver %s\n' "$host_ip" > "/etc/netns/$namespace/resolv.conf"
	echo "$namespace_ip"
}

# Filter only sandbox sources; other host traffic keeps the accept policy.
# Use IPv4 rules; redirect precedes filtering, which sees the proxy port.

install_firewall() {
	echo "==> nftables: pool $POOL_CIDR per-app endpoint restrictions or public web access"

	local rules
	rules=$(render_firewall) || return 1
	# Validate the complete replacement before changing the active firewall.
	printf '%s\n' "$rules" | nft -c -f - || return 1
	if config_query -e 'any(.apps[]; .network == "web")' >/dev/null; then
		sysctl -q -w net.ipv4.ip_forward=1 || return 1
	fi
	printf '%s\n' "$rules" | nft -f - || return 1
	install_host_forwarding
}

pool_host_ip() {
	python3 "$SCRIPT_DIR/src/read_definitions.py" network host "$POOL_BASE" "$1"
}

pool_ns_ip() {
	python3 "$SCRIPT_DIR/src/read_definitions.py" network namespace "$POOL_BASE" "$1"
}

render_firewall() {
	local rules
	rules=$(cat "$NETWORK_RULES/firewall.nft") || return 1
	rules=${rules//@POOL_CIDR@/$POOL_CIDR}
	rules=${rules//@SNI_PORT@/$SNI_PORT}
	rules=${rules//@DNS_PORT@/$DNS_PORT}
	local addresses="" app index=0
	for app in "${APPS[@]}"; do
	    if config_query -e --arg app "$app" 'any(.apps[]; .name == $app and .network == "web")' >/dev/null; then
	        addresses+="${addresses:+, }$(pool_ns_ip "$index")"
	    fi
	    index=$((index + 1))
	done
	rules=${rules//@WEB_SOURCES@/$addresses}
	printf '%s\n' "$rules"
}
