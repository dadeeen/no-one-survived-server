from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from nos_server.maintenance import DataLock
from nos_server.operations import OperationCancelled, wait_process
from nos_server.settings import Settings
from nos_server.steamcmd import UpdateError, update_server
from nos_server.supervisor import Supervisor
from nos_server.wine import prepare_wine_prefix


class MaintenanceLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        environment = patch.dict(
            os.environ,
            {
                "DATA_DIR": temporary.name,
                "RUNTIME_DIR": f"{temporary.name}/runtime",
                "UPDATE_ON_CONTAINER_START": "false",
                "PREPARE_ON_CONTAINER_START": "false",
                "START_SERVER_ON_CONTAINER_START": "true",
                "UPDATE_ON_WAKE": "false",
                "MAX_CRASH_RESTARTS": "0",
            },
            clear=True,
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.settings = Settings.from_env()
        self.settings.executable.parent.mkdir(parents=True)
        self.settings.executable.touch()

    def test_lock_is_shared_with_shell_flock_and_supports_nested_holds(self) -> None:
        lock = DataLock(self.directory)
        cancel = threading.Event()
        with lock.hold(cancel, lambda: None):
            with lock.hold(cancel, lambda: None):
                self.assertEqual(
                    subprocess.run(["flock", "-n", str(lock.path), "true"]).returncode,
                    1,
                )
            self.assertFalse(DataLock(self.directory).try_acquire())
        self.assertEqual(
            subprocess.run(["flock", "-n", str(lock.path), "true"]).returncode, 0
        )

    def test_waiting_for_maintenance_can_be_cancelled(self) -> None:
        owner = DataLock(self.directory)
        waiter = DataLock(self.directory)
        with owner.hold(threading.Event(), lambda: None):
            cancelled = threading.Event()
            cancelled.set()
            with self.assertRaises(OperationCancelled):
                with waiter.hold(cancelled, lambda: None):
                    self.fail("must not enter the protected operation")

    def test_game_holds_lock_until_stop_completes(self) -> None:
        supervisor = Supervisor(self.settings)
        supervisor.prepared = True
        other = DataLock(self.directory)
        self.addCleanup(supervisor.data_lock.release)
        with patch("nos_server.supervisor.ServerProcess") as server_process:
            server_process.return_value.start.return_value = 123
            server_process.return_value.stop.return_value = 0
            self.assertTrue(supervisor.start_server())
        self.assertFalse(other.try_acquire())
        supervisor.stop_server("test")
        self.assertTrue(other.try_acquire())
        other.release()

    def test_failed_stop_does_not_allow_save_maintenance(self) -> None:
        supervisor = Supervisor(self.settings)
        supervisor.prepared = True
        with patch("nos_server.supervisor.ServerProcess") as server_process:
            server_process.return_value.start.return_value = 123
            server_process.return_value.stop.side_effect = RuntimeError("still running")
            supervisor.start_server()
        try:
            with self.assertRaisesRegex(RuntimeError, "still running"):
                supervisor.stop_server("test")
            self.assertFalse(DataLock(self.directory).try_acquire())
        finally:
            supervisor.data_lock.release()

    def test_start_waits_for_restore_before_accessing_game_files(self) -> None:
        supervisor = Supervisor(self.settings)
        owner = DataLock(self.directory)
        entered = threading.Event()
        with patch.object(
            supervisor,
            "_start_server",
            side_effect=lambda source: entered.set() or False,
        ):
            with owner.hold(threading.Event(), lambda: None):
                thread = threading.Thread(target=supervisor.start_server)
                thread.start()
                self.assertFalse(entered.wait(0.1))
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertTrue(entered.is_set())

    def test_failed_update_blocks_wake_even_after_supervisor_restart(self) -> None:
        # UPDATE_ON_WAKE=false must not bypass a failed periodic update.
        self.settings.steamcmd_dir.mkdir(parents=True)
        (self.settings.steamcmd_dir / "steamcmd.sh").touch()
        with patch("nos_server.steamcmd._run_steamcmd", return_value=(8, False)):
            with self.assertRaises(UpdateError):
                update_server(self.settings)
        self.assertTrue(self.settings.incomplete_update_file.exists())
        supervisor = Supervisor(self.settings)
        supervisor.prepared = True
        with (
            patch.object(
                supervisor, "perform_update", side_effect=UpdateError("offline")
            ) as update,
            patch.object(supervisor.shutdown_event, "wait", return_value=False),
            patch("nos_server.supervisor.ServerProcess") as start,
        ):
            self.assertFalse(supervisor.start_server("manual"))
        update.assert_called_once()
        start.assert_not_called()
        with patch("nos_server.steamcmd._run_steamcmd", return_value=(0, False)):
            update_server(self.settings)
        self.assertFalse(self.settings.incomplete_update_file.exists())

    def test_sleep_cancels_a_wake_waiting_for_maintenance(self) -> None:
        supervisor = Supervisor(self.settings)
        supervisor.state.set_state("SLEEPING")
        owner = DataLock(self.directory)
        with patch.object(supervisor, "_start_server") as start:
            with owner.hold(threading.Event(), lambda: None):
                thread = threading.Thread(target=supervisor.start_server)
                thread.start()
                deadline = time.monotonic() + 3
                while not supervisor._start_in_progress and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(supervisor._start_in_progress)
                self.assertEqual(
                    supervisor.dispatch_control("sleep")["message"], "sleep requested"
                )
            thread.join(3)
            self.assertFalse(thread.is_alive())
            start.assert_not_called()

    def test_silent_process_has_heartbeat_and_shutdown_cancellation(self) -> None:
        cancel = threading.Event()
        heartbeat = MagicMock(side_effect=cancel.set)
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"]
        )
        try:
            with self.assertRaises(OperationCancelled):
                wait_process(process, 60, heartbeat, cancel)
            heartbeat.assert_called()
        finally:
            process.kill()
            process.wait(timeout=5)

    def test_cancelling_steamcmd_terminates_group_and_preserves_repair_marker(
        self,
    ) -> None:
        self.settings.steamcmd_dir.mkdir(parents=True)
        (self.settings.steamcmd_dir / "steamcmd.sh").touch()
        process = MagicMock()
        process.stdout = io.StringIO()
        cancel = threading.Event()

        def waiting(timeout):
            cancel.set()
            raise subprocess.TimeoutExpired("steamcmd", timeout)

        process.wait.side_effect = waiting
        with (
            patch("nos_server.steamcmd.subprocess.Popen", return_value=process),
            patch("nos_server.steamcmd._terminate_process_group") as terminate,
        ):
            with self.assertRaises(OperationCancelled):
                update_server(self.settings, cancel=cancel)
        terminate.assert_called_once_with(process)
        self.assertTrue(self.settings.incomplete_update_file.exists())
        self.assertFalse(self.settings.update_stamp.exists())

    def test_cancelling_wineboot_terminates_group(self) -> None:
        process = MagicMock()
        process.stdout = io.StringIO()
        cancel = threading.Event()

        def waiting(timeout):
            cancel.set()
            raise subprocess.TimeoutExpired("wineboot", timeout)

        process.wait.side_effect = waiting
        with (
            patch("nos_server.wine._wine_version", return_value="wine-11.0"),
            patch("nos_server.wine.subprocess.Popen", return_value=process),
            patch("nos_server.wine._terminate_process_group") as terminate,
            patch("nos_server.wine._stop_wineserver"),
        ):
            with self.assertRaises(OperationCancelled):
                prepare_wine_prefix(self.settings, cancel=cancel)
        terminate.assert_called_once_with(process)
        self.assertFalse(self.settings.wine_version_file.exists())

    def test_crash_limit_keeps_supervisor_alive_until_manual_recovery(self) -> None:
        supervisor = Supervisor(self.settings)
        supervisor.prepared = True

        def monitor():
            if supervisor.crash_restarts == 0 and start.call_count > 1:
                supervisor.shutdown_event.set()
                return "shutdown"
            return "crash"

        with (
            patch.object(supervisor, "install_signal_handlers"),
            patch.object(supervisor.control, "start"),
            patch.object(supervisor.control, "stop"),
            patch.object(supervisor, "start_server", return_value=True) as start,
            patch.object(supervisor, "monitor_server", side_effect=monitor),
        ):
            thread = threading.Thread(target=supervisor.run)
            thread.start()
            try:
                deadline = time.monotonic() + 3
                while (
                    supervisor.state.snapshot().get("state") != "ERROR"
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.01)
                self.assertEqual(supervisor.state.snapshot()["state"], "ERROR")
                self.assertTrue(thread.is_alive())
                self.assertEqual(start.call_count, 1)
                supervisor.dispatch_control("wake")
                thread.join(3)
                self.assertFalse(thread.is_alive())
                self.assertEqual(start.call_count, 2)
            finally:
                supervisor.shutdown_event.set()
                supervisor.wake_event.set()
                thread.join(3)


if __name__ == "__main__":
    unittest.main()
