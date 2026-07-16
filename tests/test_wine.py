from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from nos_server.settings import Settings
from nos_server.wine import (
    HEADLESS_WINE_DLL_OVERRIDES,
    WINEBOOT,
    WINESERVER,
    XVFB_RUN,
    WineError,
    prepare_wine_prefix,
    wine_environment,
)


class WineTests(unittest.TestCase):
    def test_wine_environment_disables_headless_helpers_by_default(self) -> None:
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
            settings = Settings.from_env()
            env = wine_environment(settings)
        self.assertEqual(env["WINEDLLOVERRIDES"], HEADLESS_WINE_DLL_OVERRIDES)

    def test_wine_environment_preserves_explicit_dll_overrides(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "WINEDLLOVERRIDES": "custom=n,b",
                },
                clear=True,
            ),
        ):
            settings = Settings.from_env()
            env = wine_environment(settings)
        self.assertEqual(env["WINEDLLOVERRIDES"], "custom=n,b")

    def test_initialized_prefix_without_marker_is_recreated(self) -> None:
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
            settings = Settings.from_env()
            settings.wine_prefix.mkdir(parents=True)
            (settings.wine_prefix / "system.reg").write_text("initialized\n")
            with (
                patch("nos_server.wine._wine_version", return_value="wine-11.0"),
                patch("nos_server.wine.shutil.rmtree") as remove_prefix,
            ):
                version = prepare_wine_prefix(settings)
        self.assertEqual(version, "wine-11.0")
        remove_prefix.assert_called_once_with(settings.wine_prefix)

    def test_xvfb_terminates_wineserver_before_waiting(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "USE_XVFB": "true",
                },
                clear=True,
            ),
        ):
            settings = Settings.from_env()
            process = MagicMock()
            process.stdout = iter(())
            process.wait.return_value = 0
            with (
                patch("nos_server.wine._wine_version", return_value="wine-11.0"),
                patch(
                    "nos_server.wine.subprocess.Popen", return_value=process
                ) as start_process,
                patch("nos_server.wine.subprocess.run") as wait_process,
            ):
                prepare_wine_prefix(settings)
        command = start_process.call_args.args[0]
        self.assertEqual(command[:4], [XVFB_RUN, "-a", "/bin/sh", "-c"])
        script = command[4]
        wineboot_index = script.index(f"{WINEBOOT} --init")
        kill_index = script.index(f"{WINESERVER} -k")
        wait_index = script.index(f"{WINESERVER} -w")
        self.assertLess(wineboot_index, kill_index)
        self.assertLess(kill_index, wait_index)
        self.assertIn('exit "$wineboot_status"', script)
        wait_process.assert_not_called()

    def test_non_xvfb_terminates_wineserver_before_waiting(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "USE_XVFB": "false",
                },
                clear=True,
            ),
        ):
            settings = Settings.from_env()
            process = MagicMock()
            process.stdout = iter(())
            process.wait.return_value = 0
            with (
                patch("nos_server.wine._wine_version", return_value="wine-11.0"),
                patch("nos_server.wine.subprocess.Popen", return_value=process),
                patch("nos_server.wine.subprocess.run") as stop_process,
            ):
                prepare_wine_prefix(settings)
        commands = [call.args[0] for call in stop_process.call_args_list]
        self.assertEqual(commands, [[WINESERVER, "-k"], [WINESERVER, "-w"]])

    def test_wineboot_timeout_terminates_the_process_group(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "WINEBOOT_TIMEOUT_SECONDS": "30",
                },
                clear=True,
            ),
        ):
            settings = Settings.from_env()
            process = MagicMock()
            process.stdout = iter(())
            process.pid = 123
            process.wait.side_effect = subprocess.TimeoutExpired("wineboot", 5)
            with (
                patch("nos_server.wine._wine_version", return_value="wine-11.0"),
                patch("nos_server.wine.subprocess.Popen", return_value=process),
                patch("nos_server.wine.time.monotonic", side_effect=[0.0, 31.0]),
                patch("nos_server.wine._terminate_process_group") as terminate,
            ):
                with self.assertRaisesRegex(WineError, "timed out"):
                    prepare_wine_prefix(settings)
        terminate.assert_called_once_with(process)


if __name__ == "__main__":
    unittest.main()
