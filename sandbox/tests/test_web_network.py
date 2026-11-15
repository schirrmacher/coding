"""Public web access is explicit, isolated by source, and overridden by offline mode."""
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from test_support import ROOT, load_module, native_config, run_bash

loader = load_module('web_definitions', ROOT / 'src/read_definitions.py')
proxy_config = load_module('web_proxy_config', ROOT / 'src/proxy_config.py')


class WebNetworkTests(unittest.TestCase):
    def test_web_mode_requires_no_endpoints_and_unknown_modes_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = native_config(root, {'demo': {'network': 'web'}})
            data = loader.read_config(config, root / 'absent')
            self.assertEqual(data['apps'][0]['network'], 'web')
            first = data['policy_fingerprint']
            (root / 'apps/demo/network').write_text('')
            self.assertNotEqual(loader.read_config(config, root / 'absent')['policy_fingerprint'], first)
            for value in ('anything', 'web\nrestricted'):
                (root / 'apps/demo/network').write_text(value)
                with self.assertRaisesRegex(ValueError, 'network'):
                    loader.read_config(config, root / 'absent')
            (root / 'apps/demo/network').write_text('web')
            (root / 'apps/demo/endpoints').write_text('example.com')
            with self.assertRaisesRegex(ValueError, 'endpoint'):
                loader.read_config(config, root / 'absent')

    def test_web_app_has_dns_but_no_sni_proxy_allowlist(self):
        endpoints = proxy_config.Endpoints('browser', [], 'web')
        self.assertTrue(endpoints.online)
        self.assertNotIn('example.com', endpoints)
        self.assertFalse(proxy_config.Endpoints('offline', []).online)
        with self.assertRaises(SystemExit):
            proxy_config.Endpoints('invalid', ['example.com'], 'web')

    def test_firewall_assigns_web_access_only_to_declared_namespace_addresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = native_config(root, {
                'allowlisted': {'endpoints': 'example.com'}, 'browser': {'network': 'web'}, 'offline': {}})
            result = run_bash(f'''source {shlex.quote(str(ROOT / 'up'))}
CONFIG={shlex.quote(str(config))}
read_config
POOL_BASE=10.77.0; POOL_CIDR=10.77.0.0/24; SNI_PORT=3128; DNS_PORT=53
mapfile -t APPS < <(config_query -r '.apps[].name')
render_firewall
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('elements = { 10.77.0.6 }', result.stdout)
            self.assertIn('ip saddr @web_sources ip daddr @non_public counter drop', result.stdout)
            self.assertIn('ip saddr @web_sources tcp dport { 80, 443 } accept', result.stdout)
            self.assertIn('ip saddr 10.77.0.0/24 tcp dport 443 redirect', result.stdout)
            self.assertIn('ip saddr 10.77.0.0/24 counter drop', result.stdout)
            self.assertNotIn('@POOL_CIDR@', result.stdout)
            self.assertNotIn('@WEB_SOURCES@', result.stdout)

    def test_invalid_firewall_does_not_replace_active_rules_or_enable_forwarding(self):
        result = run_bash(f'''source {shlex.quote(str(ROOT / 'src/configure_network.sh'))}
POOL_CIDR=10.77.0.0/24
render_firewall() {{ echo invalid; }}
nft() {{ [[ $1 == -c ]] || {{ echo unexpected-mutation; return 0; }}; return 1; }}
sysctl() {{ echo unexpected-forwarding; }}
install_firewall
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('unexpected-', result.stdout)
