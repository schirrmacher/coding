"""Render fixed-target localhost relay units from validated app definitions."""
import argparse
import json
from pathlib import Path
import sys

PROXYD = '/usr/lib/systemd/systemd-socket-proxyd'
HARDENING = '''NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictAddressFamilies=AF_INET AF_UNIX
LockPersonality=yes
'''


def render_units(data, uid):
    if not str(uid).isdecimal() or int(uid) == 0:
        raise ValueError('localhost relays require a non-root invoking user')
    units = {}
    for app in data['apps']:
        for port in app.get('localhost_ports', []):
            host = f'sandbox-localhost-host-{port}'
            address = f'/run/sandbox-localhost/{port}.sock'
            units[host + '.socket'] = f'''[Unit]
Description=Sandbox host localhost port {port}
[Socket]
ListenStream={address}
SocketUser={uid}
SocketMode=0600
DirectoryMode=0755
RemoveOnStop=yes
Service={host}.service
'''
            units[host + '.service'] = f'''[Unit]
Description=Sandbox host localhost relay {port}
Requires={host}.socket
After={host}.socket
[Service]
User={uid}
ExecStart={PROXYD} 127.0.0.1:{port}
{HARDENING}'''
            units[f'sandbox-localhost-app-{app["name"]}-{port}.service'] = f'''[Unit]
Description=Sandbox {app['name']} localhost relay {port}
Requires={host}.socket
After={host}.socket
[Service]
Type=notify
NotifyAccess=main
TimeoutStartSec=10
User={uid}
NetworkNamespacePath=/run/netns/sandbox-{app['name']}
ExecStart=/usr/bin/python3 /usr/local/lib/sandbox/localhost_relay.py --port {port} --socket {address}
{HARDENING}'''
    return units


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uid', required=True, type=int)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    for name, content in render_units(json.load(sys.stdin), args.uid).items():
        path = args.output / name
        path.write_text(content)
        path.chmod(0o644)
        print(name)
