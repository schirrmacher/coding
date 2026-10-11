"""Shared allocation for namespace setup and proxy listeners."""
from dataclasses import dataclass
import ipaddress


@dataclass(frozen=True)
class NetworkAllocation:
    host: str
    namespace: str

    @classmethod
    def at(cls, pool, index):
        if not 0 <= index < 64:
            raise ValueError("network allocation index must be between 0 and 63")
        base = int(ipaddress.IPv4Address(pool + ".0"))
        return cls(str(ipaddress.IPv4Address(base + 4 * index + 1)),
                   str(ipaddress.IPv4Address(base + 4 * index + 2)))


def proxy_config(data, pool):
    apps = []
    for index, app in enumerate(data["apps"]):
        addresses = NetworkAllocation.at(pool, index)
        apps.append({"ip": addresses.host, "netns_ip": addresses.namespace,
                     "name": app["name"], "endpoints": app["endpoints"]})
    return {"policy_fingerprint": data["policy_fingerprint"], "net": data.get("net", {}),
            "proxy": data.get("proxy", {}), "apps": apps}
