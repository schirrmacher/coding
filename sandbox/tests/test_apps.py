"""Offline desktop apps and direct agent links inside Herdr."""

import asyncio
import gzip
import json
import os
import shlex
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from test_support import ROOT, load_module, run_bash, write_config

installer = load_module("install_apps", ROOT / "lib/install_apps.py")
proxy = load_module("apps_proxy", ROOT / "proxy/sandbox_proxy.py")
loader = load_module("apps_config", ROOT / "lib/load_config.py")


def public_config(directory):
    path = Path(directory) / "sandbox/sandbox.toml"
    path.parent.mkdir(parents=True)
    path.write_text((ROOT / "sandbox.toml").read_text().replace("${HOME}", str(directory)))
    return path


class OfflineTests(unittest.TestCase):
    def test_empty_allowlist_is_valid_but_missing_and_malformed_lists_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            for endpoints, valid in (([], True), (None, False), ("example.com", False),
                                     ([""], False), (["."], False), ([123], False)):
                with self.subTest(endpoints=endpoints):
                    write_config(config, {
                        "default": "zed", "net": {"subnet": "10.77.0.0/24"},
                        "proxy": {"sni_port": 3128, "dns_port": 53},
                        "apps": [{"name": "zed", "endpoints": endpoints}],
                    })
                    result = run_bash(f'source {shlex.quote(str(ROOT / "lib/query_config.sh"))}\n'
                                      f'CONFIG={shlex.quote(str(config))}\nvalidate_config')
                    self.assertEqual(result.returncode == 0, valid, result.stderr)

    def test_offline_payloads_unshare_network_while_connected_payloads_keep_the_proxy(self):
        with tempfile.TemporaryDirectory() as directory:
            config = public_config(directory)
            ip = Path(directory) / "ip"
            ip.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\n')
            ip.chmod(0o755)
            for name in ("zed", "photocraft", "vectorcraft", "designcraft", "herdr"):
                with self.subTest(app=name):
                    result = run_bash(f'''source {shlex.quote(str(ROOT / "bin/sandbox"))}
CONFIG={shlex.quote(str(config))}; APP={name}; CMD=(/bin/true); ENV_ARGS=()
SUDO_UID=$(id -u); SUDO_GID=$(id -g)
export PATH={shlex.quote(directory)}:$PATH
prepare_directories() {{ HOME_DIR={shlex.quote(directory)}; DIRECTORIES=(); WORKING_DIRECTORY=/tmp; }}
prepare_network() {{ NS=sandbox-$APP; PROXY_HOST=10.77.0.1; PROXY_PORT=3128; }}
prepare_apparmor() {{ AA_EXEC=(); }}
run_payload
''')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    arguments = result.stdout.split("\0")
                    self.assertEqual("--unshare-net" in arguments, name != "herdr")
                    self.assertIn("--cap-drop", arguments)
                    self.assertEqual(arguments[:3], ["netns", "exec", f"sandbox-{name}"])

    def test_empty_proxy_allowlist_denies_every_hostname_without_connecting_upstream(self):
        class Writer:
            closed = False

            def get_extra_info(self, key):
                return ("10.77.0.2", 1234)

            def close(self):
                self.closed = True

        async def check():
            endpoints = proxy.Endpoints("zed", [])
            self.assertNotIn("example.com", endpoints)
            writer = Writer()
            server = proxy.SniProxy({"10.77.0.2": endpoints})
            with patch.object(server, "_read_client_hello", return_value=b"hello"), \
                    patch("sandbox_proxy_core.tls.sni_from_client_hello", return_value="example.com"), \
                    patch.object(proxy.asyncio, "open_connection") as connect:
                await server.handle(None, writer)
            connect.assert_not_called()
            self.assertTrue(writer.closed)

        asyncio.run(check())
        for entries in (None, "example.com", [""], ["."], [123]):
            with self.subTest(entries=entries), self.assertRaises(SystemExit):
                proxy.Endpoints("zed", entries)

    def test_proxy_binds_dns_only_for_connected_apps(self):
        class Server:
            async def serve_forever(self):
                return

        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "apps.json"
            config.write_text(json.dumps({
                "proxy": {"sni_port": 3128, "dns_port": 53},
                "apps": [
                    {"name": "zed", "ip": "10.77.0.1", "netns_ip": "10.77.0.2", "endpoints": []},
                    {"name": "herdr", "ip": "10.77.0.5", "netns_ip": "10.77.0.6", "endpoints": ["example.com"]},
                ],
            }))
            with patch.object(proxy.sys, "argv", ["proxy", "--apps-json", str(config)]), \
                    patch.object(proxy.asyncio, "start_server", new_callable=AsyncMock, return_value=Server()) as tcp, \
                    patch.object(proxy, "start_dns_udp", new_callable=AsyncMock) as udp, \
                    patch.object(proxy, "upstream_resolvers", return_value=["1.1.1.1"]), \
                    patch.object(proxy, "log"):
                asyncio.run(proxy.main())
            self.assertEqual([(call.args[1], call.args[2]) for call in tcp.call_args_list],
                             [("10.77.0.1", 3128), ("10.77.0.5", 3128), ("10.77.0.5", 53)])
            udp.assert_awaited_once_with("10.77.0.5", 53, ["1.1.1.1"])


class AppTests(unittest.TestCase):
    def test_creative_apps_have_home_access_without_unmasking_private_state(self):
        with tempfile.TemporaryDirectory() as directory:
            config = public_config(directory)
            with patch.object(loader, "user_home", return_value=directory):
                apps = loader.read_config(config, Path(directory) / "absent.toml")["apps"]
            by_name = {app["name"]: app for app in apps}
            for name in ("photocraft", "vectorcraft", "designcraft"):
                app = by_name[name]
                self.assertEqual(app["endpoints"], [])
                self.assertEqual(app["dir"]["write"], [directory])
                self.assertNotIn("state", app["dir"])
                self.assertTrue(app["gui"])
                fixture = Path(directory) / "fixture.toml"
                write_config(fixture, {"apps": apps})
                result = run_bash(f'''source {shlex.quote(str(ROOT / "lib/query_config.sh"))}
source {shlex.quote(str(ROOT / "lib/render_apparmor.sh"))}
CONFIG={shlex.quote(str(fixture))}
app_file_rules {name} {shlex.quote(directory)}
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f'"{directory}/**" rwklmix,', result.stdout)
                self.assertIn(f'deny "{directory}/.codex/**" rwklmx,', result.stdout)
                self.assertIn(f'deny "{fixture}" wkl,', result.stdout)
            agent_endpoints = set().union(*(set(by_name[name]["endpoints"])
                                           for name in ("claude", "codex", "opencode")))
            self.assertEqual(set(by_name["herdr"]["endpoints"]), agent_endpoints)

    def test_corrupt_download_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in installer.ASSETS:
                (Path(directory) / name).write_bytes(b"corrupt download")
            with patch.object(installer.urllib.request, "urlopen") as download:
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    installer.fetch_assets(directory)
            download.assert_not_called()

    def test_installation_is_repeatable_and_preserves_config_and_agent_state(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            assets = home / "downloads"
            assets.mkdir()
            (home / ".local/zed.app/bin").mkdir(parents=True)
            (home / ".local/zed.app/bin/zed").write_bytes(b"zed")
            (assets / "bwrap-linux-x86_64.gz").write_bytes(gzip.compress(b"helper"))
            for name in installer.ASSETS:
                if name != "bwrap-linux-x86_64.gz":
                    (assets / name).write_bytes(b"fixture")
            config = home / "sandbox.toml"
            config.write_text("preserve config")
            def version(command, **kwargs):
                if "--appimage-extract" in command:
                    icon = Path(kwargs["cwd"]) / "squashfs-root" / command[-1]
                    icon.parent.mkdir()
                    icon.write_bytes(b"icon")
                output = "herdr 0.9.3" if command[0].endswith("/herdr") else "Zed 1.23.2 fixture"
                return subprocess.CompletedProcess(command, 0, output)

            with patch.object(installer.subprocess, "run", side_effect=version), patch("builtins.print"):
                installer.install_binaries(home, assets)
                installer.install_binaries(home, assets)
            for name in ("photocraft", "vectorcraft", "designcraft"):
                self.assertEqual((home / "Applications" / f"{name}-linux.AppImage").read_bytes(), b"fixture")
                self.assertEqual((home / ".local/share/icons/hicolor/256x256/apps" /
                                  f"ai.storyteller.{name}.png").read_bytes(), b"icon")
            self.assertEqual(config.read_text(), "preserve config")
            executable = home / "agent"
            executable.write_text("raw executable")
            apps = [{"name": "codex", "cmd": ["/usr/bin/env", "PATH=/host/wrappers", str(executable)]}]
            installer.install_agent_links(home, apps)
            state = home / ".local/share/sandbox/herdr"
            (state / "codex/auth.json").write_text("preserve auth")
            installer.install_agent_links(home, apps)
            self.assertEqual((state / "bin/codex").readlink(), executable)
            self.assertEqual((state / "codex/auth.json").read_text(), "preserve auth")
            self.assertFalse((state / "bin/claude").exists())

    def test_herdr_environment_reaches_raw_agents_without_another_sandbox(self):
        with tempfile.TemporaryDirectory(prefix="herdr home ") as directory:
            home = Path(directory)
            config = public_config(directory)
            with patch.object(loader, "user_home", return_value=directory):
                apps = loader.read_config(config, home / "absent.toml")["apps"]
            herdr = next(app for app in apps if app["name"] == "herdr")
            herdr_binary = Path(herdr["cmd"][-1])
            herdr_binary.parent.mkdir(parents=True)
            herdr_binary.write_text('#!/bin/bash\nexec codex "$@"\n')
            herdr_binary.chmod(0o755)
            agent = home / "agent"
            agent.write_text('#!/usr/bin/python3 -S\nimport json,os,sys\n'
                             'print(json.dumps({"args":sys.argv[1:],"env":dict(os.environ)}))\n')
            agent.chmod(0o755)
            installer.install_agent_links(home, [{"name": "codex", "cmd": [str(agent)]}])
            result = subprocess.run([*herdr["cmd"], "two words", "a=b"], text=True, capture_output=True,
                                    env={**os.environ, **herdr.get("env", {})})
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["args"], ["two words", "a=b"])
            state = home / ".local/share/sandbox/herdr"
            for key, suffix in (("CODEX_HOME", "codex"), ("GH_CONFIG_DIR", "gh"),
                                ("CARGO_HOME", "cargo"), ("XDG_CONFIG_HOME", "config"),
                                ("UV_CACHE_DIR", "uv/cache")):
                self.assertEqual(data["env"][key], str(state / suffix))
            self.assertEqual(data["env"]["OPENCODE_DISABLE_AUTOUPDATE"], "1")

    def test_unmanaged_agent_launcher_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            launcher = home / ".local/share/sandbox/herdr/bin/codex"
            launcher.parent.mkdir(parents=True)
            launcher.write_text("user launcher")
            with self.assertRaisesRegex(ValueError, "conflicting"):
                installer.install_agent_links(home, [{"name": "codex", "cmd": ["/bin/true"]}])
            self.assertEqual(launcher.read_text(), "user launcher")

    def test_craft_icons_and_herdr_terminal_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            config = public_config(directory)
            installed = Path(directory) / "applications"
            installed.mkdir()
            (installed / "dev.zed.Zed.desktop").write_text(
                '# sandbox-managed desktop entry for app "zed"\n'
                '[Desktop Entry]\nName=Zed (sandboxed)\nIcon=herdr\n'
                'Exec=/usr/bin/env X=1 zed photocraft vectorcraft designcraft herdr\n')
            for app in ("photocraft", "vectorcraft", "designcraft", "herdr"):
                result = run_bash(f'''source {shlex.quote(str(ROOT / "bin/sandbox_wrappers"))}
HOME={shlex.quote(directory)}; CONFIG={shlex.quote(str(config))}
DESKTOP_DIR={shlex.quote(str(installed))}; BIN_DIR="$HOME/bin"; DESKTOP_BACKUP_DIR="$HOME/backups"
write_desktop_entry {app}
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                filename = "dev.herdr.Herdr.desktop" if app == "herdr" else f"ai.storyteller.{app}.desktop"
                entry = (installed / filename).read_text()
                self.assertNotIn("Name=Zed", entry)
                if app == "herdr":
                    self.assertIn("Name=Herdr\n", entry)
                    self.assertIn("Icon=herdr", entry)
                    self.assertIn("Terminal=false", entry)
                    self.assertIn("--app-id=dev.herdr.Herdr", entry)
                    self.assertNotIn("StartupWMClass=", entry)
                else:
                    self.assertIn(f"Icon={directory}/.local/share/icons/hicolor/256x256/apps/ai.storyteller.{app}.png", entry)
                    self.assertIn("Terminal=false", entry)
                    self.assertIn(f"Name={app.capitalize().replace('craft', 'Craft')}\n", entry)
                    identity = "photocraft" if app == "photocraft" else f"ai.storyteller.{app}"
                    self.assertIn(f"StartupWMClass={identity}", entry)
                if app != "herdr":
                    self.assertIn(f'Exec="{directory}/bin/{app}" %U', entry)
                else:
                    self.assertIn(f'"--" "{directory}/bin/herdr" %U', entry)
                self.assertNotIn("(sandboxed)", entry)

    def test_craft_migration_preserves_originals_and_actions_and_removes_managed_duplicates(self):
        with tempfile.TemporaryDirectory(prefix="craft launchers ") as directory:
            home = Path(directory)
            config = public_config(directory)
            config.write_text(config.read_text().replace("${HOME}", directory))
            installed, system, binaries = home / "applications", home / "system", home / "bin"
            for path in (installed, system, binaries):
                path.mkdir()
            originals = {}
            for app in ("photocraft", "vectorcraft", "designcraft"):
                original = (f"[Desktop Entry]\nName={app} (sandboxed)\nIcon=old-icon\n"
                            f"Exec={app} %F\nCategories=Graphics;\nMimeType=image/png;\n"
                            f"[Desktop Action new-window]\nName=New Window\nExec={app} --new %F\n")
                originals[app] = original
                target = installed if app == "photocraft" else system
                (target / f"ai.storyteller.{app}.desktop").write_text(original)
                (installed / f"{app}-sandboxed.desktop").write_text(
                    f'# sandbox-managed desktop entry for app "{app}"\n[Desktop Entry]\nName=Herdr\n')
            personal = installed / "personal.desktop"
            personal.write_text("[Desktop Entry]\nName=Personal\nExec=other-app\n")
            for attempt in range(2):
                result = run_bash(f'''source {shlex.quote(str(ROOT / "bin/sandbox_wrappers"))}
CONFIG={shlex.quote(str(config))}; HOME={shlex.quote(directory)}
DESKTOP_DIR="$HOME/applications"; SYSTEM_DESKTOP_DIR="$HOME/system"
DESKTOP_BACKUP_DIR="$HOME/backups"; BACKUP_DIR="$HOME/wrapper-backups"; BIN_DIR="$HOME/bin"
for app in herdr vectorcraft photocraft designcraft; do
    write_wrapper "$app"
    write_desktop_entry "$app"
done
remove_stale_launchers
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((home / "backups/ai.storyteller.photocraft.desktop").read_text(), originals["photocraft"])
                self.assertTrue(personal.exists())
                for app in originals:
                    entry = (installed / f"ai.storyteller.{app}.desktop").read_text()
                    commands = [line for line in entry.splitlines() if line.startswith("Exec=")]
                    self.assertEqual(commands, [f'Exec="{binaries}/{app}" %F',
                                                f'Exec="{binaries}/{app}" --new %F'])
                    self.assertIn("MimeType=image/png;", entry)
                    self.assertNotIn("(sandboxed)", entry)
                    self.assertFalse((installed / f"{app}-sandboxed.desktop").exists())
                    wrapper = (binaries / app).read_text()
                    self.assertIn(f"--app {app}", wrapper)
                    if app != "photocraft":
                        self.assertEqual((system / f"ai.storyteller.{app}.desktop").read_text(), originals[app])
                if attempt == 0:
                    snapshot = {path.name: path.read_bytes() for path in installed.glob("*.desktop")}
                    (installed / "ai.storyteller.photocraft.desktop").write_text(
                        originals["photocraft"].replace("photocraft %F", f'"{home}/Applications/photocraft-linux.AppImage" %F'))
                else:
                    self.assertEqual({path.name: path.read_bytes() for path in installed.glob("*.desktop")}, snapshot)

    def test_photocraft_desktop_integration_is_disabled_in_the_payload(self):
        for app in ("photocraft", "vectorcraft", "designcraft"):
            result = run_bash(f'''source {shlex.quote(str(ROOT / "bin/sandbox"))}
APP={app}; SUDO_UID=$(id -u); HOME_DIR="$HOME"; DIRECTORIES=()
prepare_mounts_and_environment
printf '%s\\0' "${{APP_ENV_ARGS[@]}}"
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            arguments = result.stdout.rstrip("\0").split("\0")
            if app == "photocraft":
                index = arguments.index("PHOTOCRAFT_NO_DESKTOP_INTEGRATION")
                self.assertEqual(arguments[index - 1:index + 2],
                                 ["--setenv", "PHOTOCRAFT_NO_DESKTOP_INTEGRATION", "1"])
            else:
                self.assertNotIn("PHOTOCRAFT_NO_DESKTOP_INTEGRATION", arguments)

    def test_zed_desktop_actions_preserve_file_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / ".local/zed.app/share/applications/dev.zed.Zed.desktop"
            source.parent.mkdir(parents=True)
            source.write_text('[Desktop Entry]\nName=Zed\nIcon=zed\nExec=zed %U\n'
                              '[Desktop Action NewWorkspace]\nExec=zed --new %U\n')
            installed = home / "applications"
            installed.mkdir()
            config = public_config(directory)
            result = run_bash(f'''source {shlex.quote(str(ROOT / "bin/sandbox_wrappers"))}
HOME={shlex.quote(directory)}; CONFIG={shlex.quote(str(config))}
BIN_DIR="$HOME/.local/bin"; DESKTOP_DIR={shlex.quote(str(installed))}; DESKTOP_BACKUP_DIR="$HOME/backups"
write_desktop_entry zed
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = (installed / source.name).read_text()
            commands = [line for line in rendered.splitlines() if line.startswith("Exec=")]
            self.assertEqual(len(commands), 2)
            for command in commands:
                self.assertTrue(command.startswith(f'Exec="{directory}/.local/bin/zed" '), command)
                self.assertTrue(command.endswith("%U"))
            self.assertTrue(commands[1].endswith("--new %U"))
            self.assertIn("Icon=dev.zed.Zed", rendered)
            self.assertIn("StartupWMClass=dev.zed.Zed", rendered)
            self.assertIn(f"TryExec={directory}/.local/bin/zed", rendered)
