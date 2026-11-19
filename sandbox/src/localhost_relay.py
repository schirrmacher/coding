"""Relay namespace-local TCP to a fixed host Unix socket."""
import argparse
import asyncio
import logging
import os
import socket


async def pump(reader, writer):
    while data := await asyncio.wait_for(reader.read(65536), 60):
        writer.write(data)
        await asyncio.wait_for(writer.drain(), 60)
    if writer.can_write_eof():
        writer.write_eof()


async def relay(reader, writer, unix_socket):
    upstream = None
    try:
        remote, upstream = await asyncio.wait_for(asyncio.open_unix_connection(unix_socket), 5)
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(pump(reader, upstream))
            tasks.create_task(pump(remote, writer))
    except (OSError, TimeoutError, ExceptionGroup) as error:
        logging.warning("localhost upstream %s: %s", unix_socket, error)
    finally:
        for stream in (writer, upstream):
            if stream is not None:
                stream.close()
                try:
                    await stream.wait_closed()
                except OSError:
                    pass


def notify_ready():
    address = os.environ.get('NOTIFY_SOCKET')
    if not address:
        return
    if address.startswith('@'):
        address = '\0' + address[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notification:
        notification.sendto(b'READY=1', address)


async def main(port, unix_socket):
    server = await asyncio.start_server(
        lambda reader, writer: relay(reader, writer, unix_socket), '127.0.0.1', port)
    async with server:
        notify_ready()
        await server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--socket', required=True)
    args = parser.parse_args()
    asyncio.run(main(args.port, args.socket))
