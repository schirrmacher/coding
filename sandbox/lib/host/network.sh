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
	echo "==> nftables: pool $POOL_CIDR limited to DNS + SNI proxy"

	nft list table ip sandbox >/dev/null 2>&1 && nft delete table ip sandbox
	nft -f - <<EOF
table ip sandbox {
	chain prerouting {
		type nat hook prerouting priority dstnat; policy accept;
		# Redirect HTTPS to the proxy, which checks SNI against the source app.
		ip saddr $POOL_CIDR tcp dport 443 redirect to :$SNI_PORT
	}
	chain input {
		type filter hook input priority 10; policy accept;
		ip saddr $POOL_CIDR tcp dport $SNI_PORT accept
		ip saddr $POOL_CIDR udp dport $DNS_PORT accept
		ip saddr $POOL_CIDR tcp dport $DNS_PORT accept
		ip saddr $POOL_CIDR counter drop
	}
	chain forward {
		type filter hook forward priority 10; policy accept;
		ip saddr $POOL_CIDR counter drop
	}
}
EOF
}

pool_host_ip() {
	python3 "$SCRIPT_DIR/../lib/network_query.py" host "$POOL_BASE" "$1"
}

pool_ns_ip() {
	python3 "$SCRIPT_DIR/../lib/network_query.py" namespace "$POOL_BASE" "$1"
}
