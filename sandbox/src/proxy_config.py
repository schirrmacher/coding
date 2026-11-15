import json
from pathlib import Path


class Endpoints:
    def __init__(self, app: str, entries: list[str], network: str = "restricted"):
        self.online = network == "web" or bool(entries)
        if network not in ("restricted", "web"):
            raise SystemExit(f"app {app!r} has invalid network mode")
        if network == "web" and entries:
            raise SystemExit(f"app {app!r} combines web access with endpoints")
        self.app = app
        if not isinstance(entries, list) or any(
            not isinstance(raw, str) or not raw.strip().rstrip(".") for raw in entries
        ):
            raise SystemExit(f"app '{app}' has invalid endpoints")
        self.entries = frozenset(
            normalized
            for raw in entries
            if (normalized := raw.strip().lower().rstrip("."))
        )

    def __contains__(self, sni: str | None) -> bool:
        return sni is not None and sni in self.entries


def load_proxy_config(config: Path) -> tuple[list[tuple[str, str, Endpoints]], int, int]:
    """Load listener IPs, namespace source IPs, endpoint lists, and ports."""
    try:
        data = json.loads(config.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read proxy config {config}: {exc}")
    apps = [
        (entry["ip"], entry["netns_ip"], Endpoints(entry["name"], entry["endpoints"], entry.get("network", "restricted")))
        for entry in data["apps"]
    ]
    if not apps:
        raise SystemExit(f"{config} declares no apps; refusing to run")

    sni_port = int(data["proxy"]["sni_port"])
    dns_port = int(data["proxy"]["dns_port"])
    return apps, sni_port, dns_port
