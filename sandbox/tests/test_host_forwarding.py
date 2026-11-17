"""Sandbox web exceptions coexist with a host FORWARD policy of DROP."""
import json
from pathlib import Path
import shlex
import tempfile
import unittest

from test_support import ROOT, native_config, run_bash


IPTABLES = '''#!/usr/bin/python3 -S
import json
import os
from pathlib import Path
import sys

path = Path(os.environ["FORWARD_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
assert args.pop(0) == "-w", "iptables must wait for the host firewall lock"
action = args.pop(0)
if state.get("fail") == action:
    sys.exit(4)
chains = state["chains"]
if action == "-S":
    print("-P FORWARD " + state["policy"])
    for name, rules in chains.items():
        if name != "FORWARD":
            print("-N " + name)
        for rule in rules:
            print("-A " + name + " " + " ".join(rule))
    sys.exit(0)
name = args.pop(0)
if action == "-N":
    if name in chains:
        sys.exit(1)
    chains[name] = []
elif action == "-F":
    chains[name] = []
elif action == "-X":
    assert not chains[name]
    assert not any(["-j", name] == rule for rules in chains.values() for rule in rules)
    del chains[name]
elif action == "-C":
    sys.exit(0 if args in chains[name] else 1)
elif action == "-D":
    chains[name].remove(args)
elif action == "-I":
    position = int(args.pop(0)) - 1
    chains[name].insert(position, args)
elif action == "-A":
    chains[name].append(args)
else:
    raise AssertionError(action)
path.write_text(json.dumps(state))
'''


class HostForwardingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = native_config(self.root / 'config', {
            'browser': {'network': 'web'}, 'restricted': {'endpoints': 'example.com'}})
        self.state = self.root / 'state.json'
        self.host_rules = [['-j', 'DOCKER-USER'], ['-j', 'DOCKER-FORWARD']]
        self.state.write_text(json.dumps({'policy': 'DROP', 'chains': {
            'FORWARD': self.host_rules, 'DOCKER-USER': [['-j', 'RETURN']],
            'DOCKER-FORWARD': [['-j', 'RETURN']]}}))
        binary = self.root / 'iptables'
        binary.write_text(IPTABLES)
        binary.chmod(0o755)

    def run_network(self, script):
        return run_bash(f'''source {shlex.quote(str(ROOT / 'up'))}
export PATH={shlex.quote(str(self.root))}:$PATH
export FORWARD_STATE={shlex.quote(str(self.state))}
CONFIG={shlex.quote(str(self.config))}
read_config
POOL_BASE=10.77.0
mapfile -t APPS < <(config_query -r '.apps[].name')
{script}
''')

    def snapshot(self):
        return json.loads(self.state.read_text())

    def test_web_exceptions_are_narrow_and_precede_unchanged_docker_rules(self):
        result = self.run_network('install_host_forwarding')
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.snapshot()
        self.assertEqual(state['policy'], 'DROP')
        self.assertEqual(state['chains']['FORWARD'], [['-j', 'SANDBOX-WEB'], *self.host_rules])
        self.assertEqual(state['chains']['DOCKER-USER'], [['-j', 'RETURN']])
        self.assertEqual(state['chains']['DOCKER-FORWARD'], [['-j', 'RETURN']])
        self.assertEqual(state['chains']['SANDBOX-WEB'], [
            ['-i', 'sbh0', '-s', '10.77.0.2/32', '-p', 'tcp', '-m', 'multiport',
             '--dports', '80,443', '-j', 'ACCEPT'],
            ['-o', 'sbh0', '-d', '10.77.0.2/32', '-m', 'conntrack',
             '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'],
        ])

    def test_repeated_setup_repositions_one_jump_and_removes_stale_rules(self):
        self.assertEqual(self.run_network('install_host_forwarding').returncode, 0)
        state = self.snapshot()
        state['chains']['FORWARD'] = [*self.host_rules, ['-j', 'SANDBOX-WEB'], ['-j', 'SANDBOX-WEB']]
        state['chains']['SANDBOX-WEB'].append(['-s', '10.77.0.99', '-j', 'ACCEPT'])
        self.state.write_text(json.dumps(state))
        result = self.run_network('install_host_forwarding; install_host_forwarding')
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.snapshot()
        self.assertEqual(state['chains']['FORWARD'], [['-j', 'SANDBOX-WEB'], *self.host_rules])
        self.assertEqual(len(state['chains']['SANDBOX-WEB']), 2)

    def test_app_address_changes_replace_previous_exceptions(self):
        self.assertEqual(self.run_network('install_host_forwarding').returncode, 0)
        native_config(self.config, {'aaa': {}})
        result = self.run_network('install_host_forwarding')
        self.assertEqual(result.returncode, 0, result.stderr)
        rules = self.snapshot()['chains']['SANDBOX-WEB']
        self.assertEqual(len(rules), 2)
        self.assertIn('sbh1', rules[0])
        self.assertIn('10.77.0.6/32', rules[0])
        self.assertIn('10.77.0.6/32', rules[1])

    def test_removing_web_access_cleans_up_only_managed_rules(self):
        self.assertEqual(self.run_network('install_host_forwarding').returncode, 0)
        (self.config / 'apps/browser/network').write_text('')
        result = self.run_network('install_host_forwarding; install_host_forwarding')
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.snapshot()
        self.assertNotIn('SANDBOX-WEB', state['chains'])
        self.assertEqual(state['chains']['FORWARD'], self.host_rules)
        self.assertEqual(state['policy'], 'DROP')

    def test_teardown_can_be_repeated(self):
        self.assertEqual(self.run_network('install_host_forwarding').returncode, 0)
        result = self.run_network(f'''source {shlex.quote(str(ROOT / 'down'))}
remove_host_forwarding
remove_host_forwarding
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('SANDBOX-WEB', self.snapshot()['chains'])
        self.assertEqual(self.snapshot()['chains']['FORWARD'], self.host_rules)

    def test_iptables_errors_propagate_even_when_caller_checks_return_status(self):
        for action in ('-S', '-N', '-F', '-A', '-C', '-I'):
            with self.subTest(action=action):
                state = self.snapshot()
                state['chains'].pop('SANDBOX-WEB', None)
                state['chains']['FORWARD'] = self.host_rules
                state['fail'] = action
                self.state.write_text(json.dumps(state))
                result = self.run_network('if install_host_forwarding; then exit 0; else exit 1; fi')
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.snapshot()['chains']['FORWARD'], self.host_rules)

    def test_web_apps_require_iptables_during_preflight(self):
        result = self.run_network('''command() { [[ $2 != iptables ]]; }
require_host_commands
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing prerequisite for web networking: iptables', result.stderr)
        self.assertEqual(self.snapshot()['chains']['FORWARD'], self.host_rules)

    def test_hosts_without_web_apps_do_not_require_iptables(self):
        (self.config / 'apps/browser/network').write_text('')
        result = self.run_network('''command() { [[ $2 != iptables ]]; }
require_host_commands
install_host_forwarding
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_policy_is_installed_before_host_exceptions(self):
        for fail_apply in (False, True):
            with self.subTest(fail_apply=fail_apply):
                result = self.run_network(f'''POOL_CIDR=10.77.0.0/24
render_firewall() {{ echo rules; }}
sysctl() {{ :; }}
nft() {{ cat >/dev/null; echo "nft $*"; [[ $1 == -c || {str(not fail_apply).lower()} == true ]]; }}
install_host_forwarding() {{ echo host-exceptions; }}
install_firewall
''')
                if fail_apply:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn('host-exceptions', result.stdout)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.splitlines()[-3:],
                                     ['nft -c -f -', 'nft -f -', 'host-exceptions'])
