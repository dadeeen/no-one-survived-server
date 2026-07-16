from __future__ import annotations

import io
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import MagicMock, patch

from nos_server import nosctl
from nos_server.control import ControlServer


class ControlServerTests(unittest.TestCase):
    def test_status_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "control.sock"
            server = ControlServer(
                path,
                lambda command: {"ok": command == "status", "command": command},
            )
            server.start()
            try:
                deadline = time.time() + 2
                while not path.exists() and time.time() < deadline:
                    time.sleep(0.01)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.connect(str(path))
                    client.sendall(b"status\n")
                    response = json.loads(client.recv(4096))
                self.assertEqual(response, {"ok": True, "command": "status"})
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            finally:
                server.stop()

    def test_start_and_cleanup_refuse_to_replace_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "control.sock"
            path.write_text("keep me", encoding="utf-8")
            server = ControlServer(path, lambda _command: {"ok": True})
            with self.assertRaisesRegex(OSError, "non-socket control path"):
                server.start()
            server.stop()
            self.assertEqual(path.read_text(encoding="utf-8"), "keep me")

    def test_stop_does_not_shutdown_a_server_whose_thread_never_started(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = ControlServer(
                Path(directory) / "control.sock", lambda _command: {"ok": True}
            )
            backend = MagicMock()
            server.server = backend
            server.thread = None
            server.stop()
        backend.shutdown.assert_not_called()
        backend.server_close.assert_called_once_with()

    def test_nosctl_times_out_when_control_server_stalls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stalled.sock"
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(path))
            listener.listen(1)
            accepted = threading.Event()

            def stall() -> None:
                connection, _ = listener.accept()
                with connection:
                    accepted.set()
                    time.sleep(0.5)

            thread = threading.Thread(target=stall)
            thread.start()
            error = io.StringIO()
            started = time.monotonic()
            try:
                with (
                    patch.dict(
                        os.environ,
                        {
                            "CONTROL_SOCKET": str(path),
                            "NOSCTL_TIMEOUT_SECONDS": "0.1",
                        },
                        clear=True,
                    ),
                    patch.object(nosctl.sys, "argv", ["nosctl", "status"]),
                    redirect_stderr(error),
                ):
                    result = nosctl.main()
                elapsed = time.monotonic() - started
            finally:
                listener.close()
                thread.join(2)
        self.assertTrue(accepted.is_set())
        self.assertEqual(result, 1)
        self.assertLess(elapsed, 1.0)
        self.assertIn("timed out", error.getvalue())

    def test_nosctl_rejects_invalid_timeout(self) -> None:
        for value in ("0", "nan", "inf", "invalid"):
            with self.subTest(value=value):
                error = io.StringIO()
                with (
                    patch.dict(
                        os.environ, {"NOSCTL_TIMEOUT_SECONDS": value}, clear=True
                    ),
                    patch.object(nosctl.sys, "argv", ["nosctl", "status"]),
                    redirect_stderr(error),
                ):
                    result = nosctl.main()
                self.assertEqual(result, 2)
                self.assertIn("control socket configuration error", error.getvalue())

    def test_nosctl_rejects_platform_timeout_overflow(self) -> None:
        client = MagicMock()
        client.__enter__.return_value.settimeout.side_effect = OverflowError(
            "timestamp too large"
        )
        error = io.StringIO()
        with (
            patch.dict(os.environ, {"NOSCTL_TIMEOUT_SECONDS": "1e308"}, clear=True),
            patch.object(nosctl.sys, "argv", ["nosctl", "status"]),
            patch("nos_server.nosctl.socket.socket", return_value=client),
            redirect_stderr(error),
        ):
            result = nosctl.main()
        self.assertEqual(result, 2)
        self.assertIn("NOSCTL_TIMEOUT_SECONDS is too large", error.getvalue())

    def test_nosctl_rejects_non_object_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "non-object.sock"
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(path))
            listener.listen(1)

            def reply() -> None:
                connection, _ = listener.accept()
                with connection:
                    connection.recv(4096)
                    connection.sendall(b"[]\n")

            thread = threading.Thread(target=reply)
            thread.start()
            error = io.StringIO()
            try:
                with (
                    patch.dict(
                        os.environ,
                        {"CONTROL_SOCKET": str(path)},
                        clear=True,
                    ),
                    patch.object(nosctl.sys, "argv", ["nosctl", "status"]),
                    redirect_stderr(error),
                ):
                    result = nosctl.main()
            finally:
                listener.close()
                thread.join(2)
        self.assertEqual(result, 1)
        self.assertIn("non-object response", error.getvalue())


if __name__ == "__main__":
    unittest.main()
