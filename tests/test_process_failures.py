from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

from nos_server import steamcmd, wine
from nos_server.settings import Settings


class PreparationFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(
            os.environ,
            {"DATA_DIR": temporary.name, "RUNTIME_DIR": f"{temporary.name}/runtime"},
            clear=True,
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.settings = Settings.from_env()
        self.settings.steamcmd_dir.mkdir(parents=True)
        (self.settings.steamcmd_dir / "steamcmd.sh").touch()

    def check_failure(self, operation: str, failure: str) -> None:
        module = steamcmd if operation == "steamcmd" else wine
        output_seen = threading.Event()
        owner = threading.current_thread()
        error = OSError("status storage unavailable")
        heartbeat_threads = []
        command = "import time; print('ready', flush=True); time.sleep(30)"
        child = subprocess.Popen(
            [sys.executable, "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        stdout = child.stdout
        self.assertIsNotNone(stdout)
        readers = []
        thread_type = threading.Thread

        def make_reader(*args, **kwargs):
            reader = thread_type(*args, **kwargs)
            readers.append(reader)
            return reader

        def log(message, **_kwargs):
            if str(message).startswith(("[steamcmd] ready", "[wineboot] ready")):
                output_seen.set()

        def heartbeat():
            heartbeat_threads.append(threading.current_thread())
            if failure == "noisy heartbeat":
                self.assertTrue(output_seen.wait(5), "output reader did not start")
            raise error

        def terminate_windows_process(process):
            # These tests exercise ownership of a real child on either platform.
            # POSIX runs the production process-group termination below.
            process.kill()
            process.wait(timeout=5)

        terminate = (
            module._terminate_process_group
            if os.name == "posix"
            else terminate_windows_process
        )
        try:
            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(module.subprocess, "Popen", return_value=child)
                )
                cleanup = stack.enter_context(
                    patch.object(module, "_terminate_process_group", wraps=terminate)
                )
                stack.enter_context(
                    patch.object(module.threading, "Thread", side_effect=make_reader)
                )
                stack.enter_context(patch("builtins.print", side_effect=log))
                stop_wine = stack.enter_context(patch.object(wine, "_stop_wineserver"))
                stack.enter_context(
                    patch.object(wine, "_wine_version", return_value="wine-11.0")
                )
                if failure == "reader start":
                    stack.enter_context(
                        patch.object(thread_type, "start", side_effect=error)
                    )
                elif failure == "missing pipe":
                    child.stdout = None
                expected = steamcmd.UpdateError if operation == "steamcmd" else OSError
                if operation == "wineboot" and failure == "missing pipe":
                    expected = wine.WineError
                with self.assertRaises(expected) as caught:
                    if operation == "steamcmd":
                        steamcmd.update_server(self.settings, heartbeat=heartbeat)
                    else:
                        wine.prepare_wine_prefix(self.settings, heartbeat=heartbeat)
                if failure != "missing pipe":
                    if operation == "steamcmd":
                        self.assertIs(caught.exception.__cause__, error)
                    else:
                        self.assertIs(caught.exception, error)
                cleanup.assert_called_once_with(child)
                self.assertIsNotNone(
                    child.poll(), "preparation child survived the error"
                )
                self.assertTrue(all(not reader.is_alive() for reader in readers))
                if failure != "missing pipe":
                    self.assertTrue(stdout.closed)
                if "heartbeat" in failure:
                    self.assertEqual(heartbeat_threads, [owner])
                if operation == "wineboot":
                    stop_wine.assert_called_once()
                    self.assertTrue(
                        (self.settings.state_dir / "wine-incomplete").exists()
                    )
                    self.assertFalse(self.settings.wine_version_file.exists())
                else:
                    stop_wine.assert_not_called()
                    self.assertTrue(self.settings.incomplete_update_file.exists())
                    self.assertFalse(self.settings.update_stamp.exists())
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
            for reader in readers:
                if reader.ident is not None:
                    reader.join(timeout=5)
            stdout.close()

    def test_steamcmd_heartbeat_failure_stops_child(self) -> None:
        self.check_failure("steamcmd", "heartbeat")

    def test_wineboot_heartbeat_failure_stops_child(self) -> None:
        self.check_failure("wineboot", "heartbeat")

    def test_steamcmd_noisy_output_keeps_heartbeat_on_owner_thread(self) -> None:
        self.check_failure("steamcmd", "noisy heartbeat")

    def test_wineboot_noisy_output_keeps_heartbeat_on_owner_thread(self) -> None:
        self.check_failure("wineboot", "noisy heartbeat")

    def test_steamcmd_reader_start_failure_stops_child(self) -> None:
        self.check_failure("steamcmd", "reader start")

    def test_wineboot_reader_start_failure_stops_child(self) -> None:
        self.check_failure("wineboot", "reader start")

    def test_steamcmd_missing_pipe_stops_child(self) -> None:
        self.check_failure("steamcmd", "missing pipe")

    def test_wineboot_missing_pipe_stops_child(self) -> None:
        self.check_failure("wineboot", "missing pipe")


class GameStartFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        from nos_server.maintenance import DataLock
        from nos_server.supervisor import Supervisor

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        with patch.dict(
            os.environ,
            {
                "DATA_DIR": temporary.name,
                "RUNTIME_DIR": f"{temporary.name}/runtime",
                "UPDATE_ON_WAKE": "false",
            },
            clear=True,
        ):
            self.supervisor = Supervisor(Settings.from_env())
        self.supervisor.prepared = True
        self.other = DataLock(directory)
        self.addCleanup(self.other.release)
        self.addCleanup(self.supervisor.data_lock.release)
        self.server = MagicMock()
        self.server.start.return_value = 123
        self.server.stop.side_effect = self.stop_while_locked
        server_class = patch(
            "nos_server.supervisor.ServerProcess", return_value=self.server
        )
        server_class.start()
        self.addCleanup(server_class.stop)

    def stop_while_locked(self):
        self.assertFalse(
            self.other.try_acquire(), "lock released before stopping the game"
        )
        return 0

    def fail_pid_write(self, **values):
        if values.get("pid") == 123:
            raise OSError("PID storage unavailable")

    def test_pid_write_failure_stops_game_before_unlocking(self) -> None:
        with patch.object(
            self.supervisor.state, "update", side_effect=self.fail_pid_write
        ):
            with self.assertRaisesRegex(OSError, "PID storage unavailable"):
                self.supervisor.start_server()
        self.server.stop.assert_called_once()
        self.assertIsNone(self.supervisor.server)
        self.assertTrue(self.other.try_acquire())

    def test_failed_pid_write_and_stop_keep_ownership_for_retry(self) -> None:
        self.server.stop.side_effect = RuntimeError("game still running")
        with patch.object(
            self.supervisor.state, "update", side_effect=self.fail_pid_write
        ):
            with self.assertRaisesRegex(OSError, "PID storage unavailable") as caught:
                self.supervisor.start_server()
        self.assertIn("game still running", " ".join(caught.exception.__notes__))
        self.assertIs(self.supervisor.server, self.server)
        self.assertFalse(self.other.try_acquire())
        self.server.stop.side_effect = self.stop_while_locked
        self.supervisor.stop_server("retry")
        self.assertIsNone(self.supervisor.server)
        self.assertTrue(self.other.try_acquire())

    def test_partial_start_and_failed_stop_keep_ownership_for_retry(self) -> None:
        self.server.start.side_effect = RuntimeError("reader start failed after spawn")
        self.server.stop.side_effect = RuntimeError("game still running")
        with self.assertRaisesRegex(RuntimeError, "reader start failed after spawn"):
            self.supervisor.start_server()
        self.assertIs(self.supervisor.server, self.server)
        self.assertFalse(self.other.try_acquire())
        self.server.stop.side_effect = self.stop_while_locked
        self.supervisor.stop_server("retry")
        self.assertTrue(self.other.try_acquire())

    def test_failed_start_with_successful_cleanup_releases_lock(self) -> None:
        self.server.start.side_effect = OSError("spawn failed")
        with self.assertRaisesRegex(OSError, "spawn failed"):
            self.supervisor.start_server()
        self.server.stop.assert_called_once()
        self.assertIsNone(self.supervisor.server)
        self.assertTrue(self.other.try_acquire())

    def test_stop_status_failure_does_not_prevent_cleanup(self) -> None:
        self.assertTrue(self.supervisor.start_server())
        with patch.object(
            self.supervisor.state, "set_state", side_effect=OSError("status failed")
        ):
            with self.assertRaisesRegex(OSError, "status failed"):
                self.supervisor.stop_server("test")
        self.server.stop.assert_called_once()
        self.assertIsNone(self.supervisor.server)
        self.assertTrue(self.other.try_acquire())


if __name__ == "__main__":
    unittest.main()
