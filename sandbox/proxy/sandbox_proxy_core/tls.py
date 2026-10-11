"""TLS ClientHello parsing, SNI filtering, and bidirectional relay."""
import asyncio

from .common import (
    CLIENT_HELLO,
    CLIENT_HELLO_LENGTH_FIELD_WIDTHS,
    CLIENT_HELLO_PREFIX_SIZE,
    HELLO_TIMEOUT,
    HOST_NAME_TYPE,
    HTTPS_PORT,
    RELAY_CHUNK_SIZE,
    SNI_EXTENSION,
    SNI_NAME_HEADER_SIZE,
    SPLICE_IDLE_TIMEOUT,
    TLS_EXTENSION_HEADER_SIZE,
    TLS_HANDSHAKE,
    TLS_HANDSHAKE_HEADER_SIZE,
    TLS_RECORD_HEADER_SIZE,
    TLS_RECORD_LENGTH_OFFSET,
    TLS_UINT16_SIZE,
    TLS_UINT8_SIZE,
    log,
)
from .config import Endpoints


class SniProxy:
    def __init__(self, apps: dict[str, Endpoints], upstream_port: int = HTTPS_PORT,
                 upstream_host: str | None = None):
        self.apps = apps
        self.upstream_port = upstream_port
        self.upstream_host = upstream_host  # fixed upstream; testing only

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        peer_ip = peer[0] if peer else "?"
        app = self.apps.get(peer_ip)
        label = app.app if app else "unknown-source"
        try:
            client_hello = await self._read_client_hello(reader)
            if client_hello is None:
                log("DENY", f"{label} {peer_ip} not-tls")
                return
            handshake = client_hello[TLS_RECORD_HEADER_SIZE:]
            sni = sni_from_client_hello(handshake)

            if app is None or sni not in app:
                log("DENY", f"{label} {peer_ip} sni={sni or 'absent'}")
                return

            try:
                destination = self.upstream_host or sni
                connection = asyncio.open_connection(destination, self.upstream_port)
                upstream_reader, upstream_writer = await asyncio.wait_for(
                    connection, HELLO_TIMEOUT,
                )
            except OSError as exc:
                log("ERROR", f"{label} sni={sni} upstream connect failed: {exc}")
                return

            log("ALLOW", f"{label} {peer_ip} sni={sni}")
            try:
                upstream_writer.write(client_hello)
                await upstream_writer.drain()
                await splice(reader, writer, upstream_reader, upstream_writer)
            finally:
                upstream_writer.close()
        except (asyncio.IncompleteReadError, asyncio.TimeoutError):
            log("DENY", f"{label} {peer_ip} no-clienthello")
        except OSError as exc:
            log("ERROR", f"{label} {peer_ip} {exc}")
        finally:
            writer.close()

    @staticmethod
    async def _read_client_hello(reader: asyncio.StreamReader) -> bytes | None:
        """Read one TLS record; None if the first bytes are not a handshake."""
        header = await asyncio.wait_for(reader.readexactly(TLS_RECORD_HEADER_SIZE), HELLO_TIMEOUT)
        if header[0] != TLS_HANDSHAKE:
            return None
        record_length = int.from_bytes(header[TLS_RECORD_LENGTH_OFFSET:TLS_RECORD_HEADER_SIZE], "big")
        body = await asyncio.wait_for(reader.readexactly(record_length), HELLO_TIMEOUT)
        return header + body


def sni_from_client_hello(hello: bytes) -> str | None:
    """Extract the server_name from a complete ClientHello, or None."""
    if len(hello) < CLIENT_HELLO_PREFIX_SIZE or hello[0] != CLIENT_HELLO:
        return None
    handshake_length = int.from_bytes(hello[TLS_UINT8_SIZE:TLS_HANDSHAKE_HEADER_SIZE], "big")
    handshake_end = TLS_HANDSHAKE_HEADER_SIZE + handshake_length
    if handshake_end > len(hello):
        return None

    offset = CLIENT_HELLO_PREFIX_SIZE
    for width in CLIENT_HELLO_LENGTH_FIELD_WIDTHS:
        if offset + width > handshake_end:
            return None
        field_length = int.from_bytes(hello[offset:offset + width], "big")
        offset += width + field_length
        if offset > handshake_end:
            return None

    extensions_start = offset + TLS_UINT16_SIZE
    if extensions_start > handshake_end:
        return None
    extensions_length = int.from_bytes(hello[offset:extensions_start], "big")
    if extensions_start + extensions_length != handshake_end:
        return None
    return sni_from_extensions(hello[extensions_start:handshake_end])


def sni_from_extensions(extensions: bytes) -> str | None:
    offset = 0
    hostname = None
    while offset < len(extensions):
        extension_start = offset + TLS_EXTENSION_HEADER_SIZE
        if extension_start > len(extensions):
            return None
        length_offset = offset + TLS_UINT16_SIZE
        extension_type = int.from_bytes(extensions[offset:length_offset], "big")
        extension_length = int.from_bytes(extensions[length_offset:extension_start], "big")
        extension_end = extension_start + extension_length
        if extension_end > len(extensions):
            return None

        if extension_type == SNI_EXTENSION:
            if hostname is not None:
                return None
            hostname = sni_from_server_name_list(extensions[extension_start:extension_end])
            if hostname is None:
                return None

        offset = extension_end
    return hostname


def sni_from_server_name_list(body: bytes) -> str | None:
    """server_name_list: 2-byte length, then (type, 2-byte len, name)."""
    if len(body) < TLS_UINT16_SIZE:
        return None
    list_length = int.from_bytes(body[:TLS_UINT16_SIZE], "big")
    if list_length != len(body) - TLS_UINT16_SIZE:
        return None

    offset = TLS_UINT16_SIZE
    hostname = None
    while offset < len(body):
        name_start = offset + SNI_NAME_HEADER_SIZE
        if name_start > len(body):
            return None
        name_type = body[offset]
        length_offset = offset + TLS_UINT8_SIZE
        name_length = int.from_bytes(body[length_offset:name_start], "big")
        name_end = name_start + name_length
        if name_length == 0 or name_end > len(body):
            return None

        if name_type == HOST_NAME_TYPE:
            if hostname is not None:
                return None
            try:
                hostname = body[name_start:name_end].decode("ascii").lower()
            except UnicodeDecodeError:
                return None

        offset = name_end
    return hostname


async def splice(
    client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter,
    upstream_reader: asyncio.StreamReader, upstream_writer: asyncio.StreamWriter,
) -> None:
    """Relay both directions until either side ends, then close both."""
    client_to_upstream = _pump(client_reader, upstream_writer)
    upstream_to_client = _pump(upstream_reader, client_writer)
    await asyncio.gather(client_to_upstream, upstream_to_client)
    client_writer.close()
    upstream_writer.close()


async def _pump(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while chunk := await asyncio.wait_for(reader.read(RELAY_CHUNK_SIZE), SPLICE_IDLE_TIMEOUT):
            writer.write(chunk)
            await writer.drain()
    except (asyncio.TimeoutError, OSError):
        pass
    finally:
        writer.close()
