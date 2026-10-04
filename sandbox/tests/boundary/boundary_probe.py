#!/usr/bin/env python3
"""Small probes used by the Bash boundary checks; never print secret contents."""
import errno
import fcntl
import os
import socket
import ssl
import sys
import tempfile
from pathlib import Path

TIMEOUT = 5
HTTPS_PORT = 443
HTTP_PROBE_BUFFER_SIZE = 1024
EXIT_BOUNDARY_FAILURE = 1
EXIT_PREREQUISITE_FAILURE = 2


def main():
    mode, *args = sys.argv[1:]
    if mode == "confinement":
        confinement()
    elif mode == "secrets":
        secrets()
    elif mode == "writable":
        writable_directory(args[0])
    elif mode == "readonly-directory":
        readonly_directory(args[0])
    elif mode == "locked-read":
        locked_read(args[0])
    elif mode == "private-directory":
        private_directory(args[0])
    elif mode == "readonly":
        readonly_fixture()
    elif mode == "readonly-config":
        readonly_config(args[0])
    elif mode == "dns":
        socket.getaddrinfo(args[0], HTTPS_PORT, type=socket.SOCK_STREAM)
    elif mode == "tls-allow":
        tls(args[0], args[0], True)
    elif mode == "tls-deny":
        tls(args[0], args[1], False)
    elif mode == "tcp-deny":
        tcp_denied(*args)
    elif mode == "http-deny":
        http_denied(*args)
    else:
        raise ValueError(f"unknown probe: {mode}")


def confinement():
    expected_home = os.environ.get("SANDBOX_TEST_CODEX_HOME")
    if expected_home:
        assert os.environ.get("CODEX_HOME") == expected_home, "CODEX_HOME differs from config"

    expected_uid = os.environ.get("SANDBOX_TEST_UID")
    if os.getuid() == 0 or (expected_uid and os.getuid() != int(expected_uid)):
        raise AssertionError("payload did not drop to the invoking user")
    status_lines = Path("/proc/self/status").read_text().splitlines()
    status = dict(line.split(":", 1) for line in status_lines if ":" in line)
    assert status["NoNewPrivs"].strip() == "1", "NoNewPrivs is unset"
    for field in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        assert int(status[field], 16) == 0, f"{field} is not empty"

    profile = Path("/proc/self/attr/current").read_text().strip()
    expected_profile = f"sandbox-{os.environ['SANDBOX_APP']} (enforce)"
    assert profile == expected_profile, "AppArmor is not enforcing"

    assert "SANDBOX_TEST_UNPASSED" not in os.environ, "host environment leaked"
    if expected_uid:
        assert os.environ.get("SANDBOX_TEST_PASSED") == "two words=a=b", "passed value changed"


def secrets():
    paths = (
        ".ssh",
        ".gnupg",
        ".aws",
        ".kube",
        ".mozilla",
        ".config/google-chrome",
        ".config/chromium",
        ".password-store",
        ".local/share/keyrings",
    )
    for relative in paths:
        path = Path.home() / relative
        try:
            with os.scandir(path) as entries:
                assert next(entries, None) is None, f"secret directory exposed: {relative}"
        except FileNotFoundError:
            print(f"SKIP absent secret directory: {relative}")
        except PermissionError:
            print(f"PASS secret access denied: {relative}")
        else:
            print(f"PASS secret directory empty: {relative}")

    credential_files = (
        ".netrc",
        ".git-credentials",
        ".config/gh/hosts.yml",
        ".claude/.credentials.json",
    )
    for relative in credential_files:
        try:
            descriptor = os.open(Path.home() / relative, os.O_RDONLY)
        except FileNotFoundError:
            print(f"SKIP absent credential file: {relative}")
        except PermissionError:
            print(f"PASS credential access denied: {relative}")
        else:
            os.close(descriptor)
            raise AssertionError(f"credential file accessible: {relative}")


def writable_directory(directory):
    fixture = os.environ.get("SANDBOX_TEST_FIXTURE")
    if fixture:
        path = Path(directory) / f".sandbox-test-{Path(fixture).name}"
        # The host runner knows this name and removes it even if the probe is killed.
        file = path.open("xb")
    else:
        file = tempfile.NamedTemporaryFile(prefix=".sandbox-test-", dir=directory, delete=False)
        path = Path(file.name)
    try:
        with file:
            file.write(b"test")
        assert path.read_bytes() == b"test"
    finally:
        path.unlink(missing_ok=True)


def readonly_directory(directory):
    with os.scandir(directory) as entries:
        next(entries, None)
    path = Path(directory) / f".sandbox-test-{Path(os.environ['SANDBOX_TEST_FIXTURE']).name}"
    try:
        file = path.open("xb")
    except OSError as error:
        if error.errno in (errno.EACCES, errno.EPERM, errno.EROFS):
            return
        raise
    file.close()
    path.unlink()
    raise AssertionError(f"shared directory is writable: {directory}")


def locked_read(filename):
    with Path(filename).open("rb") as file:
        fcntl.flock(file, fcntl.LOCK_SH)
        file.read(1)
        fcntl.flock(file, fcntl.LOCK_UN)


def private_directory(directory):
    try:
        with os.scandir(directory):
            pass
    except PermissionError:
        return
    raise AssertionError(f"other app's state directory is accessible: {directory}")


def readonly_fixture():
    fixture = os.environ.get("SANDBOX_TEST_FIXTURE")
    if not fixture:
        print("SKIP host fixture: run test_sandbox.sh --installed")
        return
    path = Path(fixture) / "control"
    assert path.read_text() == "host fixture\n", "host fixture is not visible"
    try:
        with path.open("a") as file:
            file.write("unexpected write\n")
    except PermissionError:
        return
    except OSError as error:
        if error.errno == errno.EROFS:
            return
        raise
    raise AssertionError("write outside configured directories succeeded")


def readonly_config(filename):
    path = Path(filename)
    original = path.read_bytes()
    # Check the mount before attempting operations that could damage host config.
    assert os.statvfs(path).f_flag & os.ST_RDONLY, "configuration mount is writable"

    def denied(operation, label):
        try:
            operation()
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EPERM, errno.EROFS, errno.EBUSY, errno.EXDEV):
                return
            raise
        raise AssertionError(f"configuration {label} succeeded")

    for label, flags in (("overwrite", os.O_WRONLY),
                         ("append", os.O_WRONLY | os.O_APPEND),
                         ("truncate", os.O_WRONLY | os.O_TRUNC)):
        denied(lambda: os.close(os.open(path, flags)), label)
    denied(path.unlink, "deletion")
    with tempfile.TemporaryDirectory(prefix="sandbox-config-probe-") as directory:
        replacement = Path(directory) / "replacement"
        replacement.write_bytes(original)
        denied(lambda: replacement.replace(path), "replacement")
    assert path.read_bytes() == original, "configuration contents changed"


def tls(host, name, allowed):
    context = ssl.create_default_context() if allowed else ssl._create_unverified_context()
    with socket.create_connection((host, HTTPS_PORT), timeout=TIMEOUT) as connection:
        try:
            with context.wrap_socket(connection, server_hostname=name or None):
                pass
        except (ssl.SSLError, ConnectionResetError, BrokenPipeError):
            if allowed:
                raise
            return
    assert allowed, "denied TLS handshake succeeded"


def tcp_denied(host, port):
    try:
        with socket.create_connection((host, int(port)), timeout=TIMEOUT):
            pass
    except (TimeoutError, ConnectionRefusedError):
        return
    raise AssertionError("prohibited TCP connection succeeded")


def http_denied(host, port):
    with socket.create_connection((host, int(port)), timeout=TIMEOUT) as connection:
        connection.sendall(b"GET / HTTP/1.0\r\n\r\n")
        try:
            response = connection.recv(HTTP_PROBE_BUFFER_SIZE)
        except ConnectionResetError:
            return
    assert not response, "proxy accepted plain HTTP"


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"BOUNDARY {error}", file=sys.stderr)
        sys.exit(EXIT_BOUNDARY_FAILURE)
    except (OSError, ValueError, KeyError) as error:
        print(f"CONNECTIVITY/PREREQUISITE {error}", file=sys.stderr)
        sys.exit(EXIT_PREREQUISITE_FAILURE)
