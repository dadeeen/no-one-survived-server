from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from typing import Any
from unittest.mock import patch

from nos_server.a2s import ServerInfo
from nos_server.settings import Settings
from nos_server.steamcmd import UpdateError
from nos_server.supervisor import Supervisor


class FakeState:
    def __init__(self) -> None:
        self.states: list[str] = []
        self.values: dict[str, Any] = {}

    def set_state(self, state: str, **values: Any) -> None:
        self.states.append(state)
        self.values.update(values)

    def update(self, **values: Any) -> None:
        self.values.update(values)

    def touch(self, minimum_interval: float = 5.0) -> None:
        del minimum_interval

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.states[-1] if self.states else "INITIALIZING",
            **self.values,
        }


class FakeServer:
    def __init__(self) -> None:
        self.ready = threading.Event()
        self.ready.set()

    def poll(self) -> int | None:
        return None

    def stop(self) -> int:
        return 0


class SupervisorTests(unittest.TestCase):
    def test_manual_wake_is_not_lost_during_arm_delay(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "WAKE_ARM_DELAY_SECONDS": "30",
                    "WAKE_ON_GAME_PORT": "false",
                    "WAKE_ON_QUERY_PORT": "false",
                },
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())
            supervisor.last_stop_monotonic = time.monotonic()
            supervisor.wake_event.set()
            started = time.monotonic()
            result = supervisor.wait_for_wake()
        self.assertEqual(result, "manual")
        self.assertLess(time.monotonic() - started, 1.0)

    def test_wake_command_does_not_queue_while_server_is_active(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"DATA_DIR": directory, "RUNTIME_DIR": f"{directory}/runtime"},
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())
            state = FakeState()
            state.set_state("RUNNING")
            supervisor.state = state  # type: ignore[assignment]
            response = supervisor.dispatch_control("wake")
        self.assertTrue(response["ok"])
        self.assertEqual(response["message"], "server already active")
        self.assertFalse(supervisor.wake_event.is_set())

    def test_initial_update_failure_retries_without_exiting(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "UPDATE_RETRY_DELAY_SECONDS": "5",
                },
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())
            with (
                patch.object(
                    supervisor,
                    "prepare",
                    side_effect=[UpdateError("Steam unavailable"), None],
                ) as prepare,
                patch.object(
                    supervisor.shutdown_event, "wait", return_value=False
                ) as wait,
            ):
                result = supervisor.prepare_initial(update=True)
        self.assertTrue(result)
        self.assertEqual(prepare.call_count, 2)
        wait.assert_called_once_with(5)

    def test_wake_time_update_failure_returns_to_sleep(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "UPDATE_ON_WAKE": "true",
                    "UPDATE_RETRY_DELAY_SECONDS": "5",
                },
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())
            supervisor.prepared = True
            with (
                patch.object(
                    supervisor,
                    "perform_update",
                    side_effect=UpdateError("Steam unavailable"),
                ),
                patch.object(
                    supervisor.shutdown_event, "wait", return_value=False
                ) as wait,
            ):
                result = supervisor.start_server("test wake")
            snapshot = supervisor.state.snapshot()
        self.assertFalse(result)
        self.assertIsNone(supervisor.server)
        self.assertEqual(snapshot["state"], "ERROR")
        wait.assert_called_once_with(5)

    def test_periodic_update_failure_keeps_sleeping(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "WAKE_ON_GAME_PORT": "false",
                    "WAKE_ON_QUERY_PORT": "false",
                },
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())

            def stop_after_wait(*_args: object, **_kwargs: object) -> None:
                supervisor.shutdown_event.set()

            with (
                patch("nos_server.supervisor.update_due", return_value=True),
                patch.object(
                    supervisor,
                    "perform_update",
                    side_effect=UpdateError("Steam unavailable"),
                ),
                patch(
                    "nos_server.supervisor.WakeListener.wait",
                    side_effect=stop_after_wait,
                ),
            ):
                result = supervisor.wait_for_wake()
            snapshot = supervisor.state.snapshot()
        self.assertEqual(result, "shutdown")
        self.assertEqual(snapshot["state"], "SLEEPING")

    def test_control_start_failure_is_reported_as_error(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "PREPARE_ON_CONTAINER_START": "false",
                    "UPDATE_ON_CONTAINER_START": "false",
                },
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())
            with (
                patch.object(supervisor, "install_signal_handlers"),
                patch.object(
                    supervisor.control,
                    "start",
                    side_effect=OSError("control socket unavailable"),
                ),
            ):
                result = supervisor.run()
            snapshot = supervisor.state.snapshot()
        self.assertEqual(result, 1)
        self.assertEqual(snapshot["state"], "ERROR")
        self.assertIn("control socket unavailable", str(snapshot["last_error"]))

    def test_monitor_uses_configured_a2s_host_and_keeps_idle_state(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "A2S_QUERY_HOST": "127.0.0.2",
                    "AUTO_SLEEP_ENABLED": "false",
                },
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())
            state = FakeState()
            supervisor.state = state  # type: ignore[assignment]
            supervisor.server = FakeServer()  # type: ignore[assignment]
            sleep_calls = 0

            def stop_after_second_loop(_seconds: float) -> None:
                nonlocal sleep_calls
                sleep_calls += 1
                if sleep_calls >= 2:
                    supervisor.shutdown_event.set()

            info = ServerInfo(1, "Test", "Map01", "WRSH", "NoS", 1963370, 0, 8, 0)
            with (
                patch("nos_server.supervisor.query_info", return_value=info) as query,
                patch(
                    "nos_server.supervisor.time.sleep",
                    side_effect=stop_after_second_loop,
                ),
            ):
                result = supervisor.monitor_server()
        self.assertEqual(result, "shutdown")
        query.assert_called_once_with("127.0.0.2", 27015, 2.0)
        idle_index = state.states.index("IDLE")
        self.assertNotIn("RUNNING", state.states[idle_index + 1 :])
        self.assertIsNone(state.values.get("a2s_error"))


if __name__ == "__main__":
    unittest.main()
