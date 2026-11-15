from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nos_server.settings import Settings, SettingsError


class RuntimePathTests(unittest.TestCase):
    def test_rejects_overlapping_state_and_control_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint = root / "endpoint"
            for state, control in (
                (endpoint, endpoint),
                (endpoint, endpoint / "socket"),
                (endpoint / "state.json", endpoint),
            ):
                with self.subTest(state=state, control=control):
                    with patch.dict(
                        os.environ,
                        {"STATE_FILE": str(state), "CONTROL_SOCKET": str(control)},
                        clear=True,
                    ):
                        with self.assertRaisesRegex(SettingsError, "must not overlap"):
                            Settings.from_env()

    def test_rejects_overwriting_the_maintenance_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            for name in ("STATE_FILE", "CONTROL_SOCKET"):
                with self.subTest(name=name):
                    with patch.dict(
                        os.environ,
                        {
                            "DATA_DIR": str(data),
                            name: str(data / ".nos-maintenance.lock"),
                        },
                        clear=True,
                    ):
                        with self.assertRaisesRegex(SettingsError, "maintenance lock"):
                            Settings.from_env()

    def test_runtime_endpoints_cannot_replace_persistent_markers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            state = data / "state"
            state.mkdir(parents=True)
            for marker_name in (
                "last-update",
                "last-update-attempt",
                "update-incomplete",
                "wine-version",
                "wine-incomplete",
                "generated-admin-password",
            ):
                marker = state / marker_name
                marker.write_text("retained\n", encoding="utf-8")
                for name in ("STATE_FILE", "CONTROL_SOCKET"):
                    with self.subTest(marker=marker_name, endpoint=name):
                        with patch.dict(
                            os.environ,
                            {"DATA_DIR": str(data), name: str(marker)},
                            clear=True,
                        ):
                            with self.assertRaisesRegex(
                                SettingsError, "must not overlap"
                            ):
                                Settings.from_env()
                        self.assertEqual(
                            marker.read_text(encoding="utf-8"), "retained\n"
                        )

    def test_separate_runtime_files_may_use_state_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            state_file = data / "state" / "state.json"
            control_socket = data / "state" / "control.sock"
            with patch.dict(
                os.environ,
                {
                    "DATA_DIR": str(data),
                    "STATE_FILE": str(state_file),
                    "CONTROL_SOCKET": str(control_socket),
                },
                clear=True,
            ):
                settings = Settings.from_env()
            self.assertEqual(settings.state_file, state_file)
            self.assertEqual(settings.control_socket, control_socket)

    @unittest.skipUnless(os.name == "posix", "symlinks required")
    def test_rejects_aliases_of_the_same_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real"
            real.mkdir()
            alias = root / "alias"
            alias.symlink_to(real, target_is_directory=True)
            with patch.dict(
                os.environ,
                {
                    "STATE_FILE": str(real / "endpoint"),
                    "CONTROL_SOCKET": str(alias / "endpoint"),
                },
                clear=True,
            ):
                with self.assertRaisesRegex(SettingsError, "must not overlap"):
                    Settings.from_env()


if __name__ == "__main__":
    unittest.main()
