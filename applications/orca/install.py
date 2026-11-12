"""Install the icon from an already-installed Orca AppImage."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


def install_orca_icon(home):
    home = Path(home)
    appimage = home / "Applications/orca-linux.AppImage"
    if not appimage.exists():
        return
    bundled = "usr/share/icons/hicolor/256x256/apps/orca-ide.png"
    with tempfile.TemporaryDirectory(prefix="orca-icon-") as temporary:
        subprocess.run([str(appimage), "--appimage-extract", bundled],
                       cwd=temporary, check=True, timeout=30)
        icon = home / ".local/share/icons/hicolor/256x256/apps/orca-ide.png"
        icon.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(temporary) / "squashfs-root" / bundled, icon)


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    install_orca_icon(Path.home())
