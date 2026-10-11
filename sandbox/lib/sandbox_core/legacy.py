"""Compatibility defaults for installations predating declarative desktop metadata.

New applications declare their presentation in TOML and need no entry here.
"""


def desktop_defaults(name, home):
    if name in ("photocraft", "vectorcraft", "designcraft"):
        return {"enabled": True, "id": f"ai.storyteller.{name}.desktop",
                "name": name.removesuffix("craft").capitalize() + "Craft",
                "icon": f"{home}/.local/share/icons/hicolor/256x256/apps/ai.storyteller.{name}.png",
                "window_class": "photocraft" if name == "photocraft" else f"ai.storyteller.{name}",
                "terminal": False}
    if name == "herdr":
        return {"enabled": True, "name": "Herdr", "icon": "herdr", "terminal": False,
                "id": "dev.herdr.Herdr.desktop", "terminal_app_id": "dev.herdr.Herdr"}
    if name == "zed":
        return {"template": f"{home}/.local/zed.app/share/applications/{{id}}",
                "icon": "dev.zed.Zed", "window_class": "dev.zed.Zed"}
    return {}


def environment_defaults(name):
    return {"PHOTOCRAFT_NO_DESKTOP_INTEGRATION": "1"} if name == "photocraft" else {}


def pty_default(name):
    return name == "herdr"
