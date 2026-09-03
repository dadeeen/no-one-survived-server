from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from nos_server.server_process import ServerProcess
from nos_server.settings import Settings
from nos_server.wine import WINE, XVFB_RUN, wine_environment


class ServerProcessTests(unittest.TestCase):
    def test_default_command_uses_xvfb(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"DATA_DIR": directory}, clear=True),
        ):
            command = ServerProcess(Settings.from_env()).command()
        self.assertEqual(command[:3], [XVFB_RUN, "-a", WINE])

    def test_direct_wine_command_matches_amp_template_shape(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "GAME_PORT": "7778",
                    "QUERY_PORT": "27016",
                    "EXTRA_SERVER_ARGS": '-Custom="hello world"',
                    "USE_XVFB": "false",
                },
                clear=True,
            ),
        ):
            settings = Settings.from_env()
            command = ServerProcess(settings).command()
        self.assertEqual(command[0], WINE)
        self.assertIn("WRSH", command)
        self.assertIn("-server", command)
        self.assertIn("-Port=7778", command)
        self.assertIn("-QueryPort=27016", command)
        self.assertIn("-MultiHome=0.0.0.0", command)
        self.assertIn("-Custom=hello world", command)

    def test_wine_environment_does_not_add_an_empty_library_component(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"DATA_DIR": directory}, clear=True),
        ):
            settings = Settings.from_env()
            environment = wine_environment(settings)
        self.assertEqual(environment["SteamAppId"], "1963370")
        self.assertEqual(
            environment["LD_LIBRARY_PATH"], str(settings.server_dir / "linux64")
        )

    def test_wine_environment_removes_empty_inherited_components(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "LD_LIBRARY_PATH": ":/opt/first::/opt/second:",
                },
                clear=True,
            ),
        ):
            settings = Settings.from_env()
            environment = wine_environment(settings)
        self.assertEqual(
            environment["LD_LIBRARY_PATH"],
            f"{settings.server_dir / 'linux64'}:/opt/first:/opt/second",
        )

    def test_wine_environment_uses_runtime_identity(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"DATA_DIR": directory, "USER": "root", "LOGNAME": "root"},
                clear=True,
            ),
        ):
            environment = wine_environment(Settings.from_env())
        self.assertEqual(environment["USER"], "nos")
        self.assertEqual(environment["LOGNAME"], "nos")

    def test_start_uses_safe_text_decoding(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"DATA_DIR": directory}, clear=True),
        ):
            settings = Settings.from_env()
            settings.executable.parent.mkdir(parents=True)
            settings.executable.touch()
            process = MagicMock()
            process.pid = 123
            process.stdout = iter(())
            with patch(
                "nos_server.server_process.subprocess.Popen", return_value=process
            ) as popen:
                server = ServerProcess(settings)
                self.assertEqual(server.start(), 123)
                if server._reader is not None:
                    server._reader.join(1)

        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")

    def test_stop_continues_to_sigkill_when_wineserver_times_out(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"DATA_DIR": directory}, clear=True),
        ):
            settings = Settings.from_env()
            process = MagicMock()
            process.pid = 123
            process.poll.return_value = None
            process.wait.side_effect = [
                subprocess.TimeoutExpired("server", 1),
                subprocess.TimeoutExpired("server", 1),
                -9,
            ]
            server = ServerProcess(settings)
            server.process = process
            with (
                patch("nos_server.server_process.os.killpg") as killpg,
                patch(
                    "nos_server.server_process.subprocess.run",
                    side_effect=subprocess.TimeoutExpired("wineserver", 30),
                ),
            ):
                result = server.stop()
        self.assertEqual(result, -9)
        killpg.assert_any_call(123, signal.SIGKILL)
        process.stdout.close.assert_called()

    def test_stop_uses_sigkill_sentinel_when_exit_cannot_be_reaped(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"DATA_DIR": directory}, clear=True),
        ):
            settings = Settings.from_env()
            process = MagicMock()
            process.pid = 123
            process.poll.return_value = None
            process.returncode = None
            process.wait.side_effect = [
                subprocess.TimeoutExpired("server", 1),
                subprocess.TimeoutExpired("server", 1),
                subprocess.TimeoutExpired("server", 1),
            ]
            server = ServerProcess(settings)
            server.process = process
            with (
                patch("nos_server.server_process.os.killpg"),
                patch("nos_server.server_process.subprocess.run"),
            ):
                result = server.stop()
        self.assertEqual(result, -signal.SIGKILL)

    def test_close_stops_reader_even_when_pipe_writer_stays_open(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"DATA_DIR": directory}, clear=True),
        ):
            read_fd, write_fd = os.pipe()
            stream = os.fdopen(read_fd, "r", encoding="utf-8")
            server = ServerProcess(Settings.from_env())
            process = MagicMock()
            process.stdout = stream
            server.process = process
            server._reader_stop.clear()
            server._reader = threading.Thread(target=server._read_output, daemon=True)
            server._reader.start()
            time.sleep(0.05)
            started = time.monotonic()
            try:
                server.close()
                elapsed = time.monotonic() - started
            finally:
                os.close(write_fd)

        self.assertLess(elapsed, 0.8)
        self.assertIsNone(server._reader)
        self.assertTrue(stream.closed)


if __name__ == "__main__":
    unittest.main()
