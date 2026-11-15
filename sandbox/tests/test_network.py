"""Offline desktop apps."""

import asyncio
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from test_support import ROOT, load_module, run_bash, write_config

proxy = load_module("apps_proxy", ROOT / "src/proxy.py")
loader = load_module("apps_config", ROOT / "src/read_definitions.py")


def public_config(directory):
    import shutil
    path = Path(directory) / "sandbox"
    shutil.copytree(ROOT / "apps", path / "apps")
    for source in (path / "apps").rglob("*"):
        if source.is_file():
            source.write_text(source.read_text().replace("${HOME}", str(directory)))
    return path


class OfflineTests(unittest.TestCase):
    def test_offline_payloads_unshare_network_while_connected_payloads_keep_the_proxy(self):
        with tempfile.TemporaryDirectory() as directory:
            config = public_config(directory)
            ip = Path(directory) / "ip"
            ip.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\n')
            ip.chmod(0o755)
            for app in loader.read_config(config, Path(directory) / "absent")["apps"]:
                name = app["name"]
                with self.subTest(app=name):
                    result = run_bash(f'''source {shlex.quote(str(ROOT / "run"))}
CONFIG={shlex.quote(str(config))}; APP={name}; CMD=(/bin/true); ENV_ARGS=()
SUDO_UID=$(id -u); SUDO_GID=$(id -g)
export PATH={shlex.quote(directory)}:$PATH
prepare_directories() {{ HOME_DIR={shlex.quote(directory)}; DIRECTORIES=(); WORKING_DIRECTORY=/tmp; }}
prepare_network() {{ NS=sandbox-$APP; PROXY_HOST=10.77.0.1; PROXY_PORT=3128; }}
prepare_apparmor() {{ AA_EXEC=(); }}
run_payload
''')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    arguments = result.stdout.split("\0")
                    self.assertEqual("--unshare-net" in arguments, not app["endpoints"] and app["network"] != "web")
                    self.assertIn("--cap-drop", arguments)
                    self.assertEqual(arguments[:3], ["netns", "exec", f"sandbox-{name}"])

    def test_empty_proxy_allowlist_denies_every_hostname_without_connecting_upstream(self):
        class Writer:
            closed = False

            def get_extra_info(self, key):
                return ("10.77.0.2", 1234)

            def close(self):
                self.closed = True

        async def check():
            endpoints = proxy.Endpoints("zed", [])
            self.assertNotIn("example.com", endpoints)
            writer = Writer()
            server = proxy.SniProxy({"10.77.0.2": endpoints})
            with patch.object(server, "_read_client_hello", return_value=b"hello"), \
                    patch("proxy_tls.sni_from_client_hello", return_value="example.com"), \
                    patch.object(proxy.asyncio, "open_connection") as connect:
                await server.handle(None, writer)
            connect.assert_not_called()
            self.assertTrue(writer.closed)

        asyncio.run(check())
        for entries in (None, "example.com", [""], ["."], [123]):
            with self.subTest(entries=entries), self.assertRaises(SystemExit):
                proxy.Endpoints("zed", entries)

    def test_proxy_binds_dns_only_for_connected_apps(self):
        class Server:
            async def serve_forever(self):
                return

        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "apps.json"
            config.write_text(json.dumps({
                "proxy": {"sni_port": 3128, "dns_port": 53},
                "apps": [
                    {"name": "zed", "ip": "10.77.0.1", "netns_ip": "10.77.0.2", "endpoints": []},
                    {"name": "herdr", "ip": "10.77.0.5", "netns_ip": "10.77.0.6", "endpoints": ["example.com"]},
                ],
            }))
            with patch.object(proxy.sys, "argv", ["proxy", "--apps-json", str(config)]), \
                    patch.object(proxy.asyncio, "start_server", new_callable=AsyncMock, return_value=Server()) as tcp, \
                    patch.object(proxy, "start_dns_udp", new_callable=AsyncMock) as udp, \
                    patch.object(proxy, "upstream_resolvers", return_value=["1.1.1.1"]), \
                    patch.object(proxy, "log"):
                asyncio.run(proxy.main())
            self.assertEqual([(call.args[1], call.args[2]) for call in tcp.call_args_list],
                             [("10.77.0.1", 3128), ("10.77.0.5", 3128), ("10.77.0.5", 53)])
            udp.assert_awaited_once_with("10.77.0.5", 53, ["1.1.1.1"])
