from __future__ import annotations

import json
import math
import os
import socket
import sys
from pathlib import Path


MAX_RESPONSE_BYTES = 65536


def _timeout_seconds() -> float:
    raw = os.getenv("NOSCTL_TIMEOUT_SECONDS", "5")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(
            f"NOSCTL_TIMEOUT_SECONDS must be a number, got {raw!r}"
        ) from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError("NOSCTL_TIMEOUT_SECONDS must be a positive finite number")
    return value


def main() -> int:
    command = sys.argv[1].lower() if len(sys.argv) > 1 else "status"
    if command not in {"status", "wake", "sleep"}:
        print("usage: nosctl [status|wake|sleep]", file=sys.stderr)
        return 2
    runtime_dir = Path(os.getenv("RUNTIME_DIR", "/run/nos"))
    configured_socket = os.getenv("CONTROL_SOCKET", "").strip()
    path = str(
        Path(configured_socket) if configured_socket else runtime_dir / "control.sock"
    )
    try:
        timeout = _timeout_seconds()
    except ValueError as exc:
        print(f"control socket configuration error: {exc}", file=sys.stderr)
        return 2
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(path)
            sock.sendall((command + "\n").encode())
            response = b""
            while not response.endswith(b"\n"):
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if len(response) > MAX_RESPONSE_BYTES:
                    print("control socket response is too large", file=sys.stderr)
                    return 1
    except OverflowError as exc:
        print(
            f"control socket configuration error: "
            f"NOSCTL_TIMEOUT_SECONDS is too large: {exc}",
            file=sys.stderr,
        )
        return 2
    except socket.timeout:
        print(f"control socket timed out after {timeout:g}s: {path}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"control socket error: {exc}", file=sys.stderr)
        return 1
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        print(response.decode(errors="replace"), end="")
        return 1
    if not isinstance(parsed, dict):
        print("control socket returned a non-object response", file=sys.stderr)
        return 1
    print(json.dumps(parsed, indent=2, sort_keys=True))
    return 0 if parsed.get("ok", False) else 1


if __name__ == "__main__":
    sys.exit(main())
