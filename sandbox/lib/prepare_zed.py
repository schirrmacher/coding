#!/usr/bin/env python3
"""Install Zed's desktop icon and disable telemetry without replacing user settings."""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from load_config import user_home

JSONC_TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/|[{}\[\]:,]|[^\s{}\[\]:,]+', re.S)


def disable_telemetry(source):
    tokens = [match for match in JSONC_TOKENS.finditer(source)
              if not match[0].startswith(("//", "/*"))]
    clean = ''.join(token[0] for index, token in enumerate(tokens)
                    if not (token[0] == ',' and index + 1 < len(tokens) and tokens[index + 1][0] in ('}', ']')))
    data = json.loads(clean)
    if not isinstance(data, dict) or not isinstance(data.get("telemetry", {}), dict):
        raise ValueError("Zed settings and telemetry must be objects")
    telemetry = {**data.get("telemetry", {}), "diagnostics": False, "metrics": False}
    if data.get("telemetry") == telemetry:
        return source
    replacement = json.dumps(telemetry)
    depth = 0
    for index, token in enumerate(tokens):
        if depth == 1 and token[0] == '"telemetry"' and tokens[index + 1][0] == ':':
            start = index + 2
            nesting = 0
            for value in tokens[start:]:
                nesting += (value[0] in ('{', '[')) - (value[0] in ('}', ']'))
                if nesting == 0:
                    return source[:tokens[start].start()] + replacement + source[value.end():]
        depth += (token[0] in ('{', '[')) - (token[0] in ('}', ']'))
    opening = tokens[0].end()
    return source[:opening] + '\n  "telemetry": ' + replacement + ',' + source[opening:]


def prepare_zed(home, installation):
    home, installation = Path(home), Path(installation)
    source = installation / "share/icons/hicolor/512x512/apps/zed.png"
    if not source.is_file():
        raise ValueError(f"Zed icon is missing: {source}")
    settings = home / ".config/zed/settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    original = settings.read_text() if settings.exists() else '{}\n'
    rendered = disable_telemetry(original)
    icon = home / ".local/share/icons/hicolor/512x512/apps/dev.zed.Zed.png"
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, icon)
    if settings.exists() and original == rendered:
        return
    if settings.exists():
        backup = settings.with_name("settings.json.pre-sandbox")
        if not backup.exists():
            shutil.copy2(settings, backup)
    with tempfile.NamedTemporaryFile(mode="w", dir=settings.parent, delete=False) as temporary:
        temporary.write(rendered)
        path = Path(temporary.name)
    if settings.exists():
        path.chmod(settings.stat().st_mode & 0o777)
    path.replace(settings)


if __name__ == "__main__":
    try:
        home = Path(user_home())
        prepare_zed(home, home / ".local/zed.app")
    except (OSError, ValueError) as error:
        print(f"cannot prepare Zed: {error}", file=sys.stderr)
        sys.exit(1)
