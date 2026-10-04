"""TLS hostname parsing and DNS relay behavior."""
import asyncio
import ssl
import unittest
from unittest.mock import patch

from test_support import ROOT, load_module

proxy = load_module("sandbox_proxy", ROOT / "proxy/sandbox_proxy.py")


class ProxyTests(unittest.TestCase):
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
