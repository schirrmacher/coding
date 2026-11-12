"""Initialize the isolated Brave profile without importing host browser state."""
import json
from pathlib import Path
import tempfile


def install(home):
    home = Path(home)
    for path in (home / "Downloads", home / "dev"):
        path.mkdir(parents=True, exist_ok=True)
    profile = home / ".local/share/sandbox/brave/Default"
    profile.mkdir(parents=True, exist_ok=True)
    preferences = profile / "Preferences"
    data = json.loads(preferences.read_text()) if preferences.exists() else {}
    downloads = data.setdefault("download", {})
    if "default_directory" in downloads:
        return
    downloads["default_directory"] = str(home / "Downloads")
    with tempfile.NamedTemporaryFile(mode="w", dir=profile, delete=False) as stream:
        json.dump(data, stream)
        staged = Path(stream.name)
    staged.replace(preferences)


if __name__ == "__main__":
    import argparse
    argparse.ArgumentParser(description=__doc__).parse_args()
    install(Path.home())
