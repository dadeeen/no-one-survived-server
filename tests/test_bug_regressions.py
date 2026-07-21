from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
