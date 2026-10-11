#!/usr/bin/env python3
"""Route every desktop launch action through the configured sandbox command."""

import json
import sys
from pathlib import Path


from sandbox_core.desktop import render_desktop_entry


if __name__ == "__main__":
    try:
        source = Path(sys.argv[1]).read_text()
        metadata = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
        print(render_desktop_entry(source, sys.argv[2], metadata), end="")
    except (OSError, ValueError) as error:
        print(f"cannot generate desktop entry: {error}", file=sys.stderr)
        sys.exit(1)
