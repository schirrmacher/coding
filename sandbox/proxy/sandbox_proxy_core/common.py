from __future__ import annotations

import datetime
import sys

HELLO_TIMEOUT = 5.0
# LLM streams pause for a while; only reap truly dead connections.
SPLICE_IDLE_TIMEOUT = 900.0
DNS_TIMEOUT = 5.0
RELAY_CHUNK_SIZE = 64 * 1024

HTTPS_PORT = 443
DNS_PORT = 53
DNS_TCP_LENGTH_SIZE = 2
FALLBACK_DNS_SERVER = "1.1.1.1"

TLS_HANDSHAKE = 0x16
CLIENT_HELLO = 0x01
SNI_EXTENSION = 0x0000
HOST_NAME_TYPE = 0x00

TLS_UINT8_SIZE = 1
TLS_UINT16_SIZE = 2
TLS_RECORD_HEADER_SIZE = 5
TLS_RECORD_LENGTH_OFFSET = 3
TLS_HANDSHAKE_HEADER_SIZE = 4
TLS_RANDOM_SIZE = 32
CLIENT_HELLO_PREFIX_SIZE = TLS_HANDSHAKE_HEADER_SIZE + TLS_UINT16_SIZE + TLS_RANDOM_SIZE
TLS_EXTENSION_HEADER_SIZE = 2 * TLS_UINT16_SIZE
SNI_NAME_HEADER_SIZE = TLS_UINT8_SIZE + TLS_UINT16_SIZE

# Session ID, cipher suites, and compression methods have different length widths.
CLIENT_HELLO_LENGTH_FIELD_WIDTHS = (TLS_UINT8_SIZE, TLS_UINT16_SIZE, TLS_UINT8_SIZE)


def log(event: str, detail: str) -> None:
    timestamp = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    print(f"{timestamp} {event} {detail}", file=sys.stderr, flush=True)
