"""Native definitions are discovered deterministically and parsed literally."""
import os
import shlex
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_support import ROOT, load_module, native_config, run_bash

loader = load_module("native_loader", ROOT / "src/read_definitions.py")


class ConfigTests(unittest.TestCase):
    def test_shipped_configuration_and_desktop_definitions_are_native_and_complete(self):
        data = loader.read_config(ROOT, ROOT / "tests/absent-local-apps")
        self.assertNotIn("default", data)
        apps = {app["name"]: app for app in data["apps"]}
        expected = {path.name for path in (ROOT / "apps").iterdir() if path.is_dir()}
        self.assertEqual(set(apps), expected)
        for app in apps.values():
            if "FileChooser" in app["apparmor"] and "launch.sh" in app["files"]:
                self.assertTrue(app["desktops"], app["name"])

    def test_shared_network_defaults_are_not_application_settings(self):
        data = loader.read_config(ROOT, ROOT / "tests/absent-local-apps")
        self.assertEqual(data["net"], {"subnet": "10.77.0.0/24"})
        self.assertEqual(data["proxy"], {"sni_port": 3128, "dns_port": 53})
        loader.validate_config(data)

    def test_entrypoints_and_flat_sources_are_protected_and_fingerprinted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native_config(root, {"demo": {}})
            shutil.copytree(ROOT / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__"))
            for name in ("run", "install", "up", "down"):
                shutil.copy(ROOT / name, root / name)
            with patch.object(loader, "__file__", str(root / "src/read_definitions.py")):
                first = loader.read_config(root, root / "absent")
                self.assertIn(str(root / "src"), first["config_directories"])
                for source in [*(root / name for name in ("run", "install", "up", "down")),
                               root / "src/build_mounts.sh", root / "src/proxy_tls.py"]:
                    with self.subTest(source=source.name):
                        self.assertIn(str(source), first["config_paths"])
                        original = source.read_text()
                        source.write_text(original + "\n# policy identity changes with implementation\n")
                        self.assertNotEqual(first["policy_fingerprint"],
                                            loader.read_config(root, root / "absent")["policy_fingerprint"])
                        source.write_text(original)

    def test_native_files_are_sorted_and_bind_grants_are_derived(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root, {
                "zed": {}, "codex": {"mounts.args": "--bind\n${HOME}/work with spaces\n${HOME}/work with spaces\n--ro-bind\n/usr/include\n/usr/include\n",
                                       "endpoints": "API.OPENAI.COM.\napi.openai.com\n"}})
            data = loader.read_config(path, root / "absent")
            self.assertEqual([app["name"] for app in data["apps"]], ["codex", "zed"])
            app = data["apps"][0]
            self.assertEqual(app["dir"]["write"], [str(Path.home() / "work with spaces")])
            self.assertEqual(app["dir"]["read"], ["/usr/include"])
            self.assertEqual(app["endpoints"], ["api.openai.com"])

    def test_argument_values_are_not_shell_evaluated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "never-created"
            value = f"$(touch {marker}) `touch {marker}` a=b *.py"
            path = native_config(root, {"demo": {"mounts.args": f"--setenv\nLITERAL\n{value}\n"}})
            self.assertEqual(loader.read_config(path, root / "absent")["apps"][0]["mounts"], ["--setenv", "LITERAL", value])
            self.assertFalse(marker.exists())

    def test_invalid_options_placeholders_and_paths_fail_closed(self):
        invalid = ["--\n/bin/sh\n", "--bind\n/one\n", "--bind\nrelative\n/absolute\n",
                   "--setenv\nKEY\n${UNKNOWN}\n", "--setenv\nBAD-NAME\nvalue\n", "--cap-add\nALL\n"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root, {"demo": {}})
            for text in invalid:
                with self.subTest(text=text):
                    (root / "apps/demo/mounts.args").write_text(text)
                    with self.assertRaises(ValueError):
                        loader.read_config(path, root / "absent")

    def test_required_files_app_names_and_unknown_files_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root, {"demo": {}})
            endpoints = root / "apps/demo/endpoints"
            endpoints.unlink()
            with self.assertRaisesRegex(ValueError, "missing endpoints"):
                loader.read_config(path, root / "absent")
            endpoints.write_text("")
            (root / "apps/demo/unknown").write_text("")
            with self.assertRaisesRegex(ValueError, "unknown app file"):
                loader.read_config(path, root / "absent")

    def test_empty_endpoints_means_offline_and_invalid_hostnames_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root, {"demo": {}})
            self.assertEqual(loader.read_config(path, root / "absent")["apps"][0]["endpoints"], [])
            for value in ("https://example.com", ".", "two words", "*.example.com"):
                (root / "apps/demo/endpoints").write_text(value)
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "hostnames"):
                    loader.read_config(path, root / "absent")

    def test_file_roots_and_local_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file = root / "invalid.toml"
            file.write_text("[[apps]]\n")
            with self.assertRaisesRegex(ValueError, "not a directory"):
                loader.read_config(file, root / "absent")
            path = native_config(root, {"demo": {}})
            with self.assertRaisesRegex(ValueError, "not supported"):
                loader.read_config(path, file)

    def test_symlinked_definition_root_uses_its_canonical_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root, {"demo": {}})
            other = root / "other"
            other.mkdir()
            link = other / "definitions"
            link.symlink_to(path)
            self.assertEqual(loader.read_config(path, root / "absent"), loader.read_config(link, root / "absent"))

    def test_source_files_and_definition_directories_are_protected_inside_writable_home(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root, {"demo": {"mounts.args": f"--bind\n{root}\n{root}\n",
                                                                      "apparmor": f'"{root}/**" rwklmix,\n'}})
            result = run_bash(f'''source {shlex.quote(str(ROOT / 'src/read_definitions.sh'))}
source {shlex.quote(str(ROOT / 'src/render_apparmor.sh'))}
CONFIG={shlex.quote(str(path))}
render_apparmor demo /tmp
''')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f'deny "{ROOT / "run"}" wkl,', result.stdout)
            self.assertIn(f'deny "{root}/apps/{{,**}}" wkl,', result.stdout)
            self.assertIn(f'deny "{root}/apps/demo/mounts.args" wkl,', result.stdout)

    def test_shared_includes_are_flattened_and_recursion_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root, {"demo": {"apparmor": "#include <sandbox/browser>\n"}})
            app = loader.read_config(path, root / "absent")["apps"][0]
            self.assertIn("OpenURI", app["apparmor"])
            self.assertNotIn("<sandbox/", app["apparmor"])
            self.assertNotIn("FileChooser", app["apparmor"])
            (root / "apps/demo/apparmor").write_text("#include <sandbox/missing>\n")
            with self.assertRaises(OSError):
                loader.read_config(path, root / "absent")

    def test_session_changes_do_not_stale_installed_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = native_config(root, {"demo": {"mounts.args": "--setenv\nDISPLAY\n${DISPLAY}\n"}})
            with patch.dict(os.environ, {"DISPLAY": ":1"}):
                first = loader.read_config(path, root / "absent")
            with patch.dict(os.environ, {"DISPLAY": ":2"}):
                second = loader.read_config(path, root / "absent")
            self.assertEqual(first["policy_fingerprint"], second["policy_fingerprint"])
            self.assertNotEqual(first["apps"][0]["mounts"], second["apps"][0]["mounts"])
