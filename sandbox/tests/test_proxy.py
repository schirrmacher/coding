"""TLS hostname parsing and DNS relay behavior."""
import asyncio
import ssl
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from test_support import ROOT, load_module, run_bash

proxy = load_module("sandbox_proxy", ROOT / "src/proxy.py")


class ProxyTests(unittest.TestCase):
    def test_deployed_proxy_loads_flat_modules_without_source_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            result = run_bash(f"""source {shlex.quote(str(ROOT / 'up'))}
PROXY_DIR={shlex.quote(temporary)}
POOL_BASE=10.77.0
# Keep service installation inside this fixture on hosts running systemd.
cp() {{
    if [[ $1 == */sandbox-proxy.service ]]; then
        command cp "$1" "$PROXY_DIR/sandbox-proxy.service"
    else
        command cp "$@"
    fi
}}
systemctl() {{ :; }}
install_proxy
""")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({file.name for file in runtime.glob("*.py")},
                             {"proxy.py", "proxy_common.py", "proxy_config.py", "proxy_dns.py", "proxy_tls.py"})
            result = subprocess.run(["python3", str(runtime / "proxy.py"), "--help"],
                                    cwd=runtime, env={**os.environ, "PYTHONPATH": ""},
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--apps-json", result.stdout)
            unit = (ROOT / "rules/sandbox-proxy.service").read_text()
            self.assertIn("ExecStart=/usr/bin/python3 /usr/local/lib/sandbox/proxy.py ", unit)

    def test_real_tls_client_hello_and_truncation(self):
        incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
        client = ssl.create_default_context().wrap_bio(incoming, outgoing, server_hostname="EXAMPLE.COM")
        with self.assertRaises(ssl.SSLWantReadError):
            client.do_handshake()
        record = outgoing.read()
        header_size = proxy.TLS_RECORD_HEADER_SIZE
        length_bytes = record[proxy.TLS_RECORD_LENGTH_OFFSET:header_size]
        record_length = int.from_bytes(length_bytes, "big")
        hello = record[header_size:header_size + record_length]
        self.assertEqual(proxy.sni_from_client_hello(hello), "example.com")
        for size in range(len(hello)):
            self.assertIsNone(proxy.sni_from_client_hello(hello[:size]))

    def test_malformed_server_names_are_denied(self):
        for body in (b"", b"\x00\x06\x00\x00\x09abc", b"\x00\x04\x00\x00\x01\xff"):
            with self.subTest(body=body):
                self.assertIsNone(proxy.sni_from_server_name_list(body))

    def test_dns_failure_closes_upstream(self):
        async def check():
            reader = asyncio.StreamReader()
            reader.feed_data(b"q")
            upstream = asyncio.StreamReader()
            upstream.feed_eof()

            class Writer:
                closed = False

                def write(self, data):
                    pass

                async def drain(self):
                    pass

                def close(self):
                    self.closed = True

            writer = Writer()

            async def connect(*args):
                return upstream, writer

            with patch.object(asyncio, "open_connection", connect):
                with self.assertRaises(asyncio.IncompleteReadError):
                    await proxy.relay_dns_tcp_query(b"\x00\x01", reader, Writer(), "localhost")
            self.assertTrue(writer.closed)

        asyncio.run(check())
