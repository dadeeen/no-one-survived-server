from __future__ import annotations

import json
import os
import socketserver
import stat
import threading
from collections.abc import Callable
from pathlib import Path


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        command = (
            self.rfile.readline(4096).decode("utf-8", errors="replace").strip().lower()
        )
        response = self.server.dispatch(command)  # type: ignore[attr-defined]
        self.wfile.write((json.dumps(response, sort_keys=True) + "\n").encode("utf-8"))


class _UnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

    def __init__(self, path: str, dispatch: Callable[[str], dict[str, object]]) -> None:
        self.dispatch = dispatch
        super().__init__(path, _Handler)


class ControlServer:
    def __init__(
        self, path: Path, dispatch: Callable[[str], dict[str, object]]
    ) -> None:
        self.path = path
        self.dispatch = dispatch
        self.server: _UnixServer | None = None
        self.thread: threading.Thread | None = None

    def _unlink_socket(self) -> None:
        try:
            metadata = self.path.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISSOCK(metadata.st_mode):
            self.path.unlink()

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            metadata = self.path.lstat()
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISSOCK(metadata.st_mode):
                raise OSError(
                    f"Refusing to replace non-socket control path: {self.path}"
                )
            self.path.unlink()
        self.server = _UnixServer(str(self.path), self.dispatch)
        os.chmod(self.path, 0o600)
        self.thread = threading.Thread(
            target=self.server.serve_forever, name="control-server", daemon=True
        )
        self.thread.start()

    def stop(self) -> None:
        server = self.server
        thread = self.thread
        self.server = None
        self.thread = None
        if server:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
        self._unlink_socket()
