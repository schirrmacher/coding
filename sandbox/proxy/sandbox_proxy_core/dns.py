"""UDP and TCP DNS forwarding for connected app namespaces."""
import asyncio
from pathlib import Path

from .common import (
    DNS_PORT,
    DNS_TCP_LENGTH_SIZE,
    DNS_TIMEOUT,
    FALLBACK_DNS_SERVER,
)


class DnsForwarder(asyncio.DatagramProtocol):
    def __init__(self, servers: list[str]):
        self.servers = servers
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr) -> None:
        loop = asyncio.get_running_loop()
        endpoint = loop.create_datagram_endpoint(
            lambda: DnsUplink(data, self.transport, addr),
            remote_addr=(self.servers[0], DNS_PORT),
        )
        uplink = loop.create_task(endpoint)
        uplink.add_done_callback(self._discard_failed_uplink)

    @staticmethod
    def _discard_failed_uplink(task: asyncio.Task) -> None:
        try:
            task.result()
        except OSError:
            pass  # No transport was created for an unreachable upstream.


class DnsUplink(asyncio.DatagramProtocol):
    """Forwards one query upstream and relays the first response back."""

    def __init__(self, query: bytes, reply: asyncio.DatagramTransport, client_addr):
        self.query = query
        self.reply = reply
        self.client_addr = client_addr
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport
        transport.sendto(self.query)
        asyncio.get_running_loop().call_later(DNS_TIMEOUT, transport.close)

    def datagram_received(self, data: bytes, _addr) -> None:
        self.reply.sendto(data, self.client_addr)
        self.transport.close()

    def error_received(self, _exc: Exception) -> None:
        self.transport.close()


async def handle_dns_tcp(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """TCP DNS (clients fall back to this on truncation)."""
    server = upstream_resolvers()[0]
    try:
        while length_bytes := await asyncio.wait_for(reader.readexactly(DNS_TCP_LENGTH_SIZE), DNS_TIMEOUT):
            await relay_dns_tcp_query(length_bytes, reader, writer, server)
    except (asyncio.IncompleteReadError, asyncio.TimeoutError, OSError):
        pass
    finally:
        writer.close()


async def relay_dns_tcp_query(
    length_bytes: bytes, client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter, server: str,
) -> None:
    """One query: fresh upstream connection, one response relayed back."""
    async with asyncio.timeout(DNS_TIMEOUT):
        query_length = int.from_bytes(length_bytes, "big")
        query = await client_reader.readexactly(query_length)
        upstream_reader, upstream_writer = await asyncio.open_connection(server, DNS_PORT)
        try:
            upstream_writer.write(length_bytes + query)
            await upstream_writer.drain()
            response_length_bytes = await upstream_reader.readexactly(DNS_TCP_LENGTH_SIZE)
            response_length = int.from_bytes(response_length_bytes, "big")
            response = await upstream_reader.readexactly(response_length)
            client_writer.write(response_length_bytes + response)
            await client_writer.drain()
        finally:
            upstream_writer.close()


async def start_dns_udp(ip: str, port: int, servers: list[str]) -> asyncio.DatagramTransport:
    loop = asyncio.get_running_loop()
    transport, _protocol = await loop.create_datagram_endpoint(
        lambda: DnsForwarder(servers), local_addr=(ip, port),
    )
    return transport


def upstream_resolvers() -> list[str]:
    servers = []
    for line in Path("/etc/resolv.conf").read_text().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "nameserver":
            servers.append(parts[1])
    return servers or [FALLBACK_DNS_SERVER]
