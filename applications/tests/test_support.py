from pathlib import Path
import importlib.util
import sys
ROOT = Path(__file__).resolve().parents[2] / "sandbox"
def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

import os
import subprocess
import shlex

def run_bash(script):
    return subprocess.run(["bash", "-c", "set -euo pipefail\n" + script], text=True, capture_output=True,
                          env={**os.environ, "LOCAL_CONFIG": str(ROOT / "tests/absent_local.toml")})

def write_config(path, data):
    path = Path(path)
    apps = path.parent / "apps"
    for app in data["apps"]:
        folder = apps / app["name"]
        folder.mkdir(parents=True)
        for name in ("apparmor", "mounts.args", "endpoints"):
            (folder / name).write_text("")
        (folder / "launch.sh").write_text("#!/bin/sh\nexec " + shlex.join(app["cmd"]) + ' "$@"\n')
    path.write_text('default = "' + data["apps"][0]["name"] + '"\n[net]\nsubnet="10.77.0.0/24"\n[proxy]\nsni_port=3128\ndns_port=53\n')
