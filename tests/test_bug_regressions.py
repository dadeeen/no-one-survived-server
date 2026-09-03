from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import MagicMock, patch

from nos_server import supervisor as supervisor_module
from nos_server.settings import Settings
from nos_server.steamcmd import UpdateError, update_due, update_server
from nos_server.supervisor import Supervisor


class BugRegressionTests(unittest.TestCase):
    def test_failed_update_starts_backoff_when_failure_finishes(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "UPDATE_INTERVAL_SECONDS": "60",
                    "UPDATE_RETRY_DELAY_SECONDS": "30",
                },
                clear=True,
            ),
        ):
            settings = Settings.from_env()
            with (
                patch(
                    "nos_server.steamcmd._update_server",
                    side_effect=UpdateError("Steam unavailable"),
                ),
                patch("nos_server.steamcmd.time.time", return_value=2000.0),
            ):
                with self.assertRaises(UpdateError):
                    update_server(settings)

            self.assertEqual(
                float(settings.update_attempt_stamp.read_text(encoding="ascii")),
                2000.0,
            )
            self.assertFalse(update_due(settings, now=2001.0))
            self.assertTrue(update_due(settings, now=2031.0))

    def test_sleep_requested_during_prepare_cancels_server_start(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                },
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())

            def prepare(*, initial: bool = False, update: bool = False) -> None:
                del initial, update
                supervisor.prepared = True
                supervisor.sleep_event.set()

            with (
                patch.object(supervisor, "prepare", side_effect=prepare),
                patch("nos_server.supervisor.ServerProcess") as server_process,
            ):
                started = supervisor.start_server("test wake")

            snapshot = supervisor.state.snapshot()

        self.assertFalse(started)
        self.assertIsNone(supervisor.server)
        self.assertFalse(supervisor.sleep_event.is_set())
        self.assertEqual(snapshot["state"], "SLEEPING")
        server_process.assert_not_called()

    def test_sleep_command_while_sleeping_is_not_queued(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                },
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())
            supervisor.state.set_state("SLEEPING")
            response = supervisor.dispatch_control("sleep")

        self.assertTrue(response["ok"])
        self.assertEqual(response["message"], "server already sleeping")
        self.assertFalse(supervisor.sleep_event.is_set())

    def test_fatal_error_is_not_overwritten_by_final_cleanup(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"DATA_DIR": directory, "RUNTIME_DIR": f"{directory}/runtime"},
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())
            server = MagicMock()
            server.stop.return_value = 0

            def start(_wake_source: str | None = None) -> bool:
                supervisor.server = server
                return True

            with (
                patch.object(supervisor, "install_signal_handlers"),
                patch.object(supervisor.control, "start"),
                patch.object(supervisor.control, "stop"),
                patch.object(supervisor, "prepare_initial", return_value=True),
                patch.object(supervisor, "start_server", side_effect=start),
                patch.object(
                    supervisor, "monitor_server", side_effect=OSError("disk exploded")
                ),
            ):
                result = supervisor.run()
            snapshot = supervisor.state.snapshot()

        self.assertEqual(result, 1)
        self.assertEqual(snapshot["state"], "ERROR")
        self.assertEqual(snapshot["last_error"], "disk exploded")

    def test_stale_log_source_cannot_change_current_player_count(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"DATA_DIR": directory, "RUNTIME_DIR": f"{directory}/runtime"},
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())
            old_server = MagicMock()
            current_server = MagicMock()
            supervisor._activate_log_source(current_server)
            supervisor.state.update(log_players=0)
            supervisor._log_activity(old_server, 1)
            stale_snapshot = supervisor.state.snapshot()
            supervisor._log_activity(current_server, 2)
            current_snapshot = supervisor.state.snapshot()

        self.assertEqual(stale_snapshot["log_players"], 0)
        self.assertEqual(current_snapshot["log_players"], 2)

    def test_crash_path_closes_server_reader_before_dropping_reference(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"DATA_DIR": directory, "RUNTIME_DIR": f"{directory}/runtime"},
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())
            server = MagicMock()
            server.poll.return_value = 23
            supervisor.server = server
            result = supervisor.monitor_server()
            snapshot = supervisor.state.snapshot()

        self.assertEqual(result, "crash")
        server.close.assert_called_once_with()
        self.assertIsNone(supervisor.server)
        self.assertEqual(snapshot["last_exit_code"], 23)

    def test_first_wake_uses_retrying_preparation_path(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"DATA_DIR": directory, "RUNTIME_DIR": f"{directory}/runtime"},
                clear=True,
            ),
        ):
            supervisor = Supervisor(Settings.from_env())
            with (
                patch.object(
                    supervisor, "prepare_initial", return_value=False
                ) as prepare,
                patch("nos_server.supervisor.ServerProcess") as server_process,
            ):
                result = supervisor.start_server("wake packet")

        self.assertFalse(result)
        prepare.assert_called_once_with(
            update=True,
            context="Wake preparation",
        )
        server_process.assert_not_called()

    def test_state_initialisation_failure_is_reported_as_configuration_error(
        self,
    ) -> None:
        error = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"DATA_DIR": directory, "RUNTIME_DIR": f"{directory}/runtime"},
                clear=True,
            ),
            patch.object(
                supervisor_module,
                "StateStore",
                side_effect=PermissionError("read-only runtime"),
            ),
            redirect_stderr(error),
        ):
            result = supervisor_module.main()

        self.assertEqual(result, 2)
        self.assertIn("cannot initialise state file", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())


if __name__ == "__main__":
    unittest.main()
