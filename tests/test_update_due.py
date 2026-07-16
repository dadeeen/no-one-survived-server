from __future__ import annotations

import os
import tempfile
import time
import unittest
from unittest.mock import patch

from nos_server.settings import Settings
from nos_server.steamcmd import UpdateError, update_due, update_server


class UpdateDueTests(unittest.TestCase):
    def test_disabled_interval_is_never_due(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"DATA_DIR": directory, "UPDATE_INTERVAL_SECONDS": "0"},
                clear=True,
            ),
        ):
            settings = Settings.from_env()
            self.assertFalse(update_due(settings))

    def test_old_stamp_is_due(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"DATA_DIR": directory, "UPDATE_INTERVAL_SECONDS": "60"},
                clear=True,
            ),
        ):
            settings = Settings.from_env()
            settings.state_dir.mkdir(parents=True)
            settings.update_stamp.write_text(
                str(int(time.time()) - 120), encoding="ascii"
            )
            self.assertTrue(update_due(settings))

    def test_recent_failed_attempt_uses_retry_backoff(self) -> None:
        now = 10_000.0
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "UPDATE_INTERVAL_SECONDS": "60",
                    "UPDATE_RETRY_DELAY_SECONDS": "30",
                },
                clear=True,
            ),
        ):
            settings = Settings.from_env()
            settings.state_dir.mkdir(parents=True)
            settings.update_attempt_stamp.write_text("9990\n", encoding="ascii")
            self.assertFalse(update_due(settings, now=now))
            self.assertTrue(update_due(settings, now=10_021.0))

    def test_newer_failed_attempt_does_not_hide_recent_success_forever(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "UPDATE_INTERVAL_SECONDS": "100",
                    "UPDATE_RETRY_DELAY_SECONDS": "30",
                },
                clear=True,
            ),
        ):
            settings = Settings.from_env()
            settings.state_dir.mkdir(parents=True)
            settings.update_stamp.write_text("1000\n", encoding="ascii")
            settings.update_attempt_stamp.write_text("1110\n", encoding="ascii")
            self.assertFalse(update_due(settings, now=1120.0))
            self.assertTrue(update_due(settings, now=1141.0))

    def test_operating_system_failures_are_normalized_to_update_error(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"DATA_DIR": directory}, clear=True),
        ):
            settings = Settings.from_env()
            with patch(
                "nos_server.steamcmd._update_server",
                side_effect=OSError("cannot start SteamCMD"),
            ):
                with self.assertRaisesRegex(UpdateError, "cannot start SteamCMD"):
                    update_server(settings)


if __name__ == "__main__":
    unittest.main()
