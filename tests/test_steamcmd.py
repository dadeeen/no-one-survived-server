from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from nos_server.settings import Settings
from nos_server.steamcmd import UpdateError, update_server


class FakeProcess:
    def __init__(
        self,
        return_code: int = 0,
        timeout: bool = False,
        output: list[str] | None = None,
    ) -> None:
        self.stdout = iter(output or ["output\n"])
        self.pid = 12345
        self.return_code = return_code
        self.timeout = timeout
        self.wait_timeouts: list[float | int | None] = []

    def wait(self, timeout: float | int | None = None) -> int:
        self.wait_timeouts.append(timeout)
        if self.timeout:
            raise subprocess.TimeoutExpired("steamcmd", timeout)
        return self.return_code

    def kill(self) -> None:
        pass


class SteamCmdTests(unittest.TestCase):
    def _settings(self, directory: str) -> Settings:
        with patch.dict(
            os.environ,
            {
                "DATA_DIR": directory,
                "STEAMCMD_TIMEOUT_SECONDS": "120",
            },
            clear=True,
        ):
            settings = Settings.from_env()
        settings.steamcmd_dir.mkdir(parents=True)
        (settings.steamcmd_dir / "steamcmd.sh").touch()
        settings.executable.parent.mkdir(parents=True)
        settings.executable.touch()
        return settings

    def test_update_uses_safe_decoding_and_configured_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = self._settings(directory)
            process = FakeProcess()
            with patch(
                "nos_server.steamcmd.subprocess.Popen", return_value=process
            ) as popen:
                update_server(settings)

            kwargs = popen.call_args.kwargs
            self.assertEqual(kwargs["encoding"], "utf-8")
            self.assertEqual(kwargs["errors"], "replace")
            self.assertTrue(kwargs["start_new_session"])
            self.assertEqual(process.wait_timeouts, [120])
            self.assertTrue(settings.update_attempt_stamp.exists())
            self.assertTrue(settings.update_stamp.exists())

    def test_missing_configuration_refreshes_metadata_and_retries_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = self._settings(directory)
            settings.executable.unlink()
            first = FakeProcess(
                return_code=8,
                output=[
                    "ERROR! Failed to install app '2329680' (Missing configuration)\n"
                ],
            )
            second = FakeProcess()

            def start_process(*args: object, **kwargs: object) -> FakeProcess:
                del args, kwargs
                if first.wait_timeouts:
                    settings.executable.touch()
                    return second
                return first

            with (
                patch(
                    "nos_server.steamcmd.subprocess.Popen",
                    side_effect=start_process,
                ) as popen,
                patch("nos_server.steamcmd.time.sleep") as sleep,
            ):
                update_server(settings)

            self.assertEqual(popen.call_count, 2)
            sleep.assert_called_once_with(30)
            first_command = popen.call_args_list[0].args[0]
            second_command = popen.call_args_list[1].args[0]
            self.assertNotIn("+app_info_update", first_command)
            metadata_index = second_command.index("+app_info_update")
            self.assertEqual(second_command[metadata_index + 1], "1")
            self.assertLess(metadata_index, second_command.index("+app_update"))
            self.assertTrue(settings.update_stamp.exists())

    def test_unrelated_failure_does_not_use_metadata_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = self._settings(directory)
            settings.executable.unlink()
            process = FakeProcess(return_code=8, output=["ERROR! Network failure\n"])
            with (
                patch(
                    "nos_server.steamcmd.subprocess.Popen", return_value=process
                ) as popen,
                patch("nos_server.steamcmd.time.sleep") as sleep,
            ):
                with self.assertRaises(UpdateError):
                    update_server(settings)

            popen.assert_called_once()
            sleep.assert_not_called()

    def test_timeout_is_reported_as_update_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = self._settings(directory)
            process = FakeProcess(timeout=True)
            with (
                patch("nos_server.steamcmd.subprocess.Popen", return_value=process),
                patch("nos_server.steamcmd._terminate_process_group") as terminate,
            ):
                with self.assertRaises(UpdateError):
                    update_server(settings)
        terminate.assert_called_once_with(process)


if __name__ == "__main__":
    unittest.main()
