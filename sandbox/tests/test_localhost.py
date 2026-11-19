"""Explicit host-loopback services keep application namespaces isolated."""
import asyncio
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

from test_support import ROOT, load_module, native_config, run_bash

loader = load_module('localhost_definitions', ROOT / 'src/read_definitions.py')
services = load_module('localhost_services', ROOT / 'src/localhost_services.py')
relay = load_module('localhost_relay', ROOT / 'src/localhost_relay.py')


class LocalhostConfigTests(unittest.TestCase):
    def test_ports_are_opt_in_and_personal_replacements_can_remove_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = native_config(root / 'public', {
                'enabled': {'localhost-ports': '# host service\n8765\n8765\n\n'}, 'disabled': {}})
            local = root / 'local'
            data = loader.read_config(config, local)
            apps = {app['name']: app for app in data['apps']}
            self.assertEqual(apps['enabled']['localhost_ports'], [8765])
            self.assertEqual(apps['disabled']['localhost_ports'], [])
            directory = local / 'enabled'
            directory.mkdir(parents=True)
            (directory / 'localhost-ports').write_text('')
            replaced = loader.read_config(config, local)
            self.assertEqual(replaced['apps'][1]['localhost_ports'], [])
            self.assertNotEqual(data['policy_fingerprint'], replaced['policy_fingerprint'])

    def test_invalid_ports_are_rejected_before_service_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = native_config(root, {'demo': {'localhost-ports': ''}})
            for content in ('0', '80', '65536', '-1', '127.0.0.1:8765', '8765/tcp', '8765\nExecStart=bad'):
                with self.subTest(content=content):
                    (config / 'apps/demo/localhost-ports').write_text(content)
                    with self.assertRaisesRegex(ValueError, 'localhost-ports'):
                        loader.read_config(config, root / 'absent')

    def test_default_access_is_limited_to_opencode_orca_and_uv(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = loader.read_config(ROOT, Path(temporary) / 'absent')
            enabled = {app['name']: app['localhost_ports'] for app in data['apps'] if app['localhost_ports']}
            self.assertEqual(enabled, {'opencode': [8765], 'orca': [8765], 'uv': [8765]})


class LocalhostUnitTests(unittest.TestCase):
    def test_namespaces_share_one_fixed_host_socket_without_tcp_host_listeners(self):
        data = {'apps': [{'name': 'orca', 'localhost_ports': [8765]},
                         {'name': 'uv', 'localhost_ports': [8765]}, {'name': 'other'}]}
        units = services.render_units(data, 1000)
        self.assertEqual(len(units), 4)
        host = units['sandbox-localhost-host-8765.service']
        self.assertIn('systemd-socket-proxyd 127.0.0.1:8765', host)
        socket = units['sandbox-localhost-host-8765.socket']
        self.assertIn('ListenStream=/run/sandbox-localhost/8765.sock', socket)
        self.assertIn('SocketUser=1000\nSocketMode=0600', socket)
        for app in ('orca', 'uv'):
            unit = units[f'sandbox-localhost-app-{app}-8765.service']
            self.assertIn(f'NetworkNamespacePath=/run/netns/sandbox-{app}', unit)
            self.assertIn('Type=notify', unit)
            self.assertIn('User=1000', unit)
            self.assertIn('ProtectHome=yes', unit)
            self.assertIn('NoNewPrivileges=yes', unit)
            self.assertIn('CapabilityBoundingSet=\n', unit)
        self.assertFalse(any('other' in name for name in units))

    def test_services_require_an_unprivileged_invoking_user(self):
        for uid in (0, 'invalid', '-1'):
            with self.subTest(uid=uid), self.assertRaises(ValueError):
                services.render_units({'apps': []}, uid)

    def test_address_reassignment_keeps_relays_attached_to_the_named_namespace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = native_config(root, {'demo': {'localhost-ports': '8765'}})
            before = services.render_units(loader.read_config(config, root / 'absent'), 1000)
            native_config(config, {'aaa': {}})
            after = services.render_units(loader.read_config(config, root / 'absent'), 1000)
            self.assertEqual(before, after)


class LocalhostRelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.socket = str(Path(temporary.name) / 'host.sock')
        self.server = await asyncio.start_server(
            lambda reader, writer: relay.relay(reader, writer, self.socket), '127.0.0.1', 0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.addAsyncCleanup(self.close_server, self.server)

    async def close_server(self, server):
        server.close()
        await server.wait_closed()

    async def request(self, payload):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
        writer.write(payload)
        await writer.drain()
        writer.write_eof()
        try:
            try:
                return await asyncio.wait_for(reader.read(), 3)
            except ConnectionResetError:
                return b''
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionResetError:
                pass

    async def test_requests_and_half_closed_uploads_cross_the_unix_bridge(self):
        requests = []

        async def host(reader, writer):
            requests.append(await reader.read())
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok')
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        upstream = await asyncio.start_unix_server(host, self.socket)
        self.addAsyncCleanup(self.close_server, upstream)
        payload = b'GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n'
        response = await self.request(payload)
        self.assertTrue(response.endswith(b'\r\n\r\nok'))
        self.assertEqual(requests, [payload])

    async def test_new_connections_recover_when_the_upstream_becomes_available(self):
        with self.assertLogs(level='WARNING'):
            self.assertEqual(await self.request(b'health'), b'')

        async def host(reader, writer):
            await reader.read()
            writer.write(b'healthy')
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        upstream = await asyncio.start_unix_server(host, self.socket)
        self.addAsyncCleanup(self.close_server, upstream)
        self.assertEqual(await self.request(b'health'), b'healthy')

    async def test_an_occupied_namespace_port_does_not_report_readiness(self):
        with patch.object(relay, 'notify_ready') as ready:
            with self.assertRaises(OSError):
                await relay.main(self.port, self.socket)
            ready.assert_not_called()


class LocalhostLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = native_config(self.root / 'config', {'demo': {'localhost-ports': '8765'}})
        self.units = self.root / 'units'
        self.units.mkdir()
        self.runtime = self.root / 'runtime'
        self.runtime.mkdir()
        self.calls = self.root / 'calls'

    def run_lifecycle(self, script):
        return run_bash(f'''source {shlex.quote(str(ROOT / 'up'))}
CONFIG={shlex.quote(str(self.config))}
PROXY_DIR={shlex.quote(str(self.runtime))}
LOCALHOST_UNIT_DIR={shlex.quote(str(self.units))}
SUDO_UID=1000
read_config
systemctl() {{ printf '%s\\n' "$*" >> {shlex.quote(str(self.calls))}; }}
{script}
''')

    def test_repeated_setup_replaces_units_and_removal_preserves_unrelated_services(self):
        unrelated = self.units / 'unrelated.service'
        unrelated.write_text('keep')
        result = self.run_lifecycle('install_localhost_services; install_localhost_services')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(self.units.glob('sandbox-localhost-*'))), 3)
        self.assertTrue((self.runtime / 'localhost_relay.py').is_file())
        self.assertIn('sandbox-localhost-app-demo-8765.service', self.calls.read_text())
        (self.config / 'apps/demo/localhost-ports').write_text('')
        result = self.run_lifecycle('install_localhost_services; remove_localhost_services; remove_localhost_services')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.units.iterdir()), [unrelated])
        self.assertEqual(unrelated.read_text(), 'keep')

    def test_changed_ports_replace_stale_listeners(self):
        self.assertEqual(self.run_lifecycle('install_localhost_services').returncode, 0)
        (self.config / 'apps/demo/localhost-ports').write_text('8766')
        result = self.run_lifecycle('install_localhost_services')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all('8766' in path.name for path in self.units.iterdir()))

    def test_service_start_failure_propagates_and_stops_partial_startup(self):
        result = self.run_lifecycle('''systemctl() {
    printf '%s\\n' "$*" >> ''' + shlex.quote(str(self.calls)) + '''
    [[ $1 != start ]]
}
if install_localhost_services; then exit 0; else exit 1; fi
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.calls.read_text().splitlines()[-1].startswith('stop '))

    def test_stop_failure_prevents_deleting_owned_units(self):
        self.assertEqual(self.run_lifecycle('install_localhost_services').returncode, 0)
        before = list(self.units.iterdir())
        result = self.run_lifecycle('''systemctl() { return 1; }
if remove_localhost_services; then exit 0; else exit 1; fi
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.units.iterdir()), before)

    def test_busy_application_restores_relays_after_policy_update_is_refused(self):
        self.assertEqual(self.run_lifecycle('install_localhost_services').returncode, 0)
        (self.runtime / 'apps.json').write_text('{"policy_fingerprint": "stale"}')
        self.calls.write_text('')
        result = self.run_lifecycle('''ip() {
    if [[ "$*" == 'netns list' ]]; then echo sandbox-demo; else echo 123; fi
}
load_config
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sandbox-demo is in use', result.stderr)
        calls = self.calls.read_text().splitlines()
        self.assertTrue(calls[0].startswith('stop '))
        self.assertTrue(calls[-1].startswith('start '))

    def test_status_reports_relay_state_without_probing_the_upstream(self):
        for active in (True, False):
            with self.subTest(active=active):
                result = self.run_lifecycle(f'''source {shlex.quote(str(ROOT / 'src/show_status.sh'))}
systemctl() {{ return {0 if active else 1}; }}
print_localhost_status
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"localhost: demo 127.0.0.1:8765 {'active' if active else 'inactive'}", result.stdout)

    def test_missing_prerequisites_do_not_install_units(self):
        result = self.run_lifecycle('''SOCKET_PROXY=/nonexistent/socket-proxyd
require_localhost_commands
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue('requires systemd' in result.stderr or 'missing prerequisite' in result.stderr)
        self.assertEqual(list(self.units.iterdir()), [])
