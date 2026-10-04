#!/usr/bin/env bash
# Host-side download/build checks; requires installed wrappers and sandbox up.
set -euo pipefail

SANDBOX_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CONFIG="$SANDBOX_ROOT/sandbox.toml"
source "$SANDBOX_ROOT/lib/query_config.sh"
TOOL_FIXTURE=

cleanup_tool_fixture() {
	[[ -z $TOOL_FIXTURE ]] || rm -rf -- "$TOOL_FIXTURE"
}

main() {
	local app project wrapper
	local -a apps=("$@")
	[[ ${#apps[@]} -gt 0 ]] || apps=(cargo uv)
	for app in "${apps[@]}"; do
		[[ $app == cargo || $app == uv ]] || {
			echo "usage: bash sandbox/tests/test_tools.sh [cargo|uv]..." >&2
			return 2
		}
	done
	read_config
	trap cleanup_tool_fixture EXIT
	trap 'exit 130' INT
	trap 'exit 143' TERM
	for app in "${apps[@]}"; do
		if [[ $app == cargo ]] && ! PATH=/usr/local/bin:/usr/bin:/bin command -v cc >/dev/null; then
			echo "ERROR missing host C linker (cc); on Ubuntu/Debian/Zorin, run sudo apt install build-essential" >&2
			return 2
		fi
		wrapper="$HOME/.local/bin/$app"
		[[ -f $wrapper && ! -L $wrapper ]] && grep -q "sandbox-managed wrapper for app \"$app\"" "$wrapper" || {
			echo "ERROR missing sandbox wrapper: $wrapper; run make install-sandbox from the host" >&2
			return 2
		}
		project=$(app_project_directories "$app" "$PWD" | head -n1)
		TOOL_FIXTURE=$(mktemp -d "$project/.sandbox-tool-test.XXXXXX")
		cp "$SANDBOX_ROOT/tests/boundary/boundary_probe.py" "$TOOL_FIXTURE/boundary_probe.py"
		cat > "$TOOL_FIXTURE/child_probe.py" <<'PY'
import errno
import os
import sys
import tempfile
from pathlib import Path
from boundary_probe import confinement, secrets, tls

confinement()
secrets()
try:
    with tempfile.NamedTemporaryFile(dir="/var/tmp"):
        pass
except OSError as error:
    assert error.errno in (errno.EACCES, errno.EPERM, errno.EROFS), error
else:
    raise AssertionError("child can write outside project/state")
tls(os.environ["SANDBOX_PROXY_HOST"], "blocked.sandbox-test.invalid", False)
if os.environ["SANDBOX_APP"] == "cargo":
    assert os.statvfs(Path.home() / ".rustup").f_flag & os.ST_RDONLY
else:
    import idna
    assert idna.encode("example.com") == b"example.com"
    assert Path(sys.base_prefix).is_relative_to(os.environ["UV_PYTHON_INSTALL_DIR"])
print("PASS child confinement")
PY
		(
			cd "$TOOL_FIXTURE"
			"$wrapper" --version
			if [[ $app == cargo ]]; then
				mkdir src
				cat > Cargo.toml <<'TOML'
[package]
name = "sandbox-smoke"
version = "0.1.0"
edition = "2021"
[dependencies]
itoa = "=1.0.15"
TOML
				cat > build.rs <<'RS'
fn main() {
    let probe = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("child_probe.py");
    let status = std::process::Command::new("python3").arg(probe).status().unwrap();
    assert!(status.success(), "build script child escaped confinement or could not run");
}
RS
				cat > src/lib.rs <<'RS'
#[test]
fn downloaded_dependency_works() {
    assert_eq!(itoa::Buffer::new().format(42), "42");
}
RS
				"$wrapper" test
				"$wrapper" test --offline
			else
				cat > pyproject.toml <<'TOML'
[project]
name = "sandbox-smoke"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["idna==3.10"]
TOML
				"$wrapper" python install 3.12
				"$wrapper" sync --managed-python --python 3.12
				"$wrapper" run --offline --managed-python --python 3.12 python child_probe.py
				"$wrapper" sync --offline --managed-python --python 3.12
			fi
		)
		echo "PASS $app downloads, persistent cache, and child confinement"
		cleanup_tool_fixture
		TOOL_FIXTURE=
	done
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
	main "$@"
fi
