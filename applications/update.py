"""Install verified cached releases without changing sandbox policy or launchers."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile


import argparse

def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=root / ".app-updates")
    args = parser.parse_args()
    cache = args.cache_dir
    from craft import install as install_apps
    from orca.install import install_orca_icon

    assets = {}
    for app in ('photocraft', 'vectorcraft', 'designcraft', 'orca'):
        release = json.loads((cache / f'{app}-latest.json').read_text())
        asset = next(a for a in release['assets'] if a['name'] == 'orca-linux.AppImage' or a['name'].endswith('-linux-x86_64.AppImage'))
        if app != 'orca':
            url, expected = install_apps.ASSETS[asset['name']]
        else:
            url, expected = asset['browser_download_url'], asset['digest'].removeprefix('sha256:')
        destination = cache / (f"orca-{release['tag_name']}.AppImage" if app == 'orca' else asset['name'])
        if not destination.exists():
            temporary = Path(str(destination) + '.tmp')
            result = subprocess.run(['curl', '-fL', '--retry', '2', url, '-o', str(temporary)])
            if result.returncode:
                subprocess.run(['curl', '-fL', '--retry', '2',
                                '-H', 'Accept: application/octet-stream', asset['url'],
                                '-o', str(temporary)], check=True)
            with temporary.open('rb') as file:
                if hashlib.file_digest(file, 'sha256').hexdigest() != expected:
                    raise ValueError(f'Checksum mismatch: {temporary}')
            temporary.replace(destination)
        with destination.open('rb') as file:
            if hashlib.file_digest(file, 'sha256').hexdigest() != expected:
                raise ValueError(f'Checksum mismatch: {destination}')
        assets[app] = (release, asset, destination)
        print(f"Verified {app} {release['tag_name']}", flush=True)

    if args.download_only:
        return

    install_apps.fetch_assets(cache)
    install_apps.install_binaries(Path.home(), cache)
    source = assets['orca'][2]
    destination = Path.home() / 'Applications/orca-linux.AppImage'
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.orca-', delete=False) as temporary:
        staged = Path(temporary.name)
    try:
        shutil.copy2(source, staged)
        staged.chmod(0o755)
        staged.replace(destination)
    finally:
        staged.unlink(missing_ok=True)
    install_orca_icon(Path.home())
    print('Installed Orca ' + assets['orca'][0]['tag_name'])


if __name__ == "__main__":
    main()
