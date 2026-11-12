"""Every declared app satisfies the same native launch and isolation contracts."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import tomllib
import unittest

from test_support import ROOT, load_module, run_bash, write_global_config

loader = load_module('contract_definitions', ROOT / 'lib/read_definitions.py')
desktop = load_module('contract_desktops', ROOT / 'lib/render_desktop.py')


class AppContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.home = Path(cls.temporary.name)
        cls.config = cls.home / 'sandbox.toml'
        settings = tomllib.loads((ROOT / 'sandbox.toml').read_text())
        write_global_config(cls.config, {key: settings[key] for key in ('default', 'net', 'proxy')})
        shutil.copytree(ROOT / 'apps', cls.home / 'apps')
        cls.data = loader.read_config(cls.config, cls.home / 'absent', home=str(cls.home))
        loader.validate_config(cls.data)
        cls.apps = {app['name']: app for app in cls.data['apps']}

    def declaration_contract(self, name):
        app = self.apps[name]
        self.assertTrue({'apparmor', 'mounts.args', 'endpoints'} <= app['files'].keys())
        self.assertNotIn('prepare.sh', app['files'])
        self.assertNotIn('#include <sandbox/', app['apparmor'])
        self.assertIn(app['network'], ('restricted', 'web'))
        if app['network'] == 'web':
            self.assertEqual(app['endpoints'], [])
            self.assertIn('--tmpfs', app['mounts'])
            self.assertEqual(app['mounts'][app['mounts'].index('--tmpfs') + 1], str(self.home))
            self.assertNotIn(str(self.home), app['dir']['write'])
            self.assertNotIn('org.freedesktop.secrets', app['apparmor'])
            self.assertNotIn('--no-sandbox', Path(app['files']['launch.sh']).read_text())
        for mode in ('write', 'read'):
            for directory in app['dir'][mode]:
                self.assertTrue(Path(directory).is_absolute())
        for state in app['dir'].get('state', []):
            for other in self.data['apps']:
                if other['name'] == name:
                    continue
                shared = {path for paths in other['dir'].values() for path in paths}
                if state not in shared:
                    self.assertIn(state, loader.AppPolicy.from_config(self.data, other['name']).private)

    def launch_contract(self, name):
        app = self.apps[name]
        script = app['files'].get('launch.sh')
        if script:
            environment = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin'}
            command = ['/bin/sh', script, '--sandbox-command', '/usr/bin/printf', '%s\n', 'two words', 'a=b']
            result = subprocess.run(command, env=environment, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'two words\na=b\n')
            configured = [shlex.split(line)[1:3] for line in Path(script).read_text().splitlines()
                          if line.startswith('sandbox_env ')]
            result = subprocess.run(['/bin/sh', script, '--sandbox-command', '/usr/bin/env'],
                                    env=environment, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            values = dict(line.split('=', 1) for line in result.stdout.splitlines())
            for key, value in configured:
                self.assertEqual(values[key], value.replace('${HOME}', str(self.home)))
            overrides = {key: '' for key, _ in configured}
            overrides.update(PATH='/explicit path', SANDBOX_ENV_OVERRIDES=':'.join([*overrides, 'PATH']))
            result = subprocess.run(['/bin/sh', script, '--sandbox-command', '/usr/bin/env'],
                                    env={**environment, **overrides}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            values = dict(line.split('=', 1) for line in result.stdout.splitlines())
            for key, value in overrides.items():
                self.assertEqual(values[key], value)
        # Command-only apps also receive the complete namespace and mask plan.
        result = run_bash(f'''source {shlex.quote(str(ROOT / 'bin/sandbox'))}
CONFIG={shlex.quote(str(self.config))}; APP={shlex.quote(name)}
HOME_DIR={shlex.quote(str(self.home))}; CMD=(/bin/true); ENV_ARGS=()
prepare_mounts_and_environment
printf '%s\\n' "${{NETWORK_ARGS[@]}}"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        offline = not app['endpoints'] and app['network'] != 'web'
        self.assertEqual('--unshare-net' in result.stdout, offline)
        result = run_bash(f'''source {shlex.quote(str(ROOT / 'bin/sandbox'))}
CONFIG={shlex.quote(str(self.config))}; APP={shlex.quote(name)}
HOME_DIR={shlex.quote(str(self.home))}; CMD=(/bin/true); ENV_ARGS=(); OFFLINE=1
prepare_mounts_and_environment
printf '%s\\n' "${{NETWORK_ARGS[@]}}"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--unshare-net', result.stdout)


    def desktop_contract(self, name):
        app = self.apps[name]
        for filename, source in app['desktops'].items():
            with self.subTest(desktop=filename):
                prefix = '/sandbox/wrapper '
                rendered = desktop.render_native_desktop(source, prefix, '/sandbox/wrapper')
                original = [line for line in source.splitlines() if line.startswith('Exec=')]
                commands = [line for line in rendered.splitlines() if line.startswith('Exec=')]
                self.assertEqual(len(commands), len(original))
                self.assertTrue(all(prefix in line for line in commands))
                self.assertIn('TryExec=/sandbox/wrapper', rendered)
                for field in ('Icon=', 'StartupWMClass=', 'MimeType='):
                    for line in source.splitlines():
                        if line.startswith(field):
                            self.assertIn(line, rendered)


for directory in sorted((ROOT / 'apps').iterdir()):
    if directory.is_dir():
        for contract in ('declaration', 'launch', 'desktop'):
            def test(self, name=directory.name, operation=contract):
                getattr(self, operation + '_contract')(name)
            setattr(AppContracts, f'test_{directory.name.replace("-", "_")}_{contract}', test)
