from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nos_server.configuration import apply_configuration, build_updates
from nos_server.settings import Settings, SettingsError


class ConfigurationTests(unittest.TestCase):
    def test_known_and_json_overrides(self) -> None:
        env = {
            "SERVER_NAME": "Home Server",
            "PVP": "true",
            "MAX_PLAYERS": "6",
            "GAME_INI_OVERRIDES": '{"Future":{"Setting":42}}',
        }
        with patch.dict(os.environ, env, clear=True):
            updates, applied = build_updates()
        self.assertEqual(updates["ServerSetting"]["ServerName"], "Home Server")
        self.assertEqual(updates["ServerSetting"]["MaxPlayers"], "6")
        self.assertEqual(updates["GameSettings"]["PVP"], "True")
        self.assertEqual(updates["Future"]["Setting"], "42")
        self.assertTrue(applied)

    def test_secret_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "secret"
            secret.write_text("safe-password\n", encoding="utf-8")
            with patch.dict(
                os.environ, {"ADMIN_PASSWORD_FILE": str(secret)}, clear=True
            ):
                updates, _ = build_updates()
            self.assertEqual(updates["ServerSetting"]["AdminPassword"], "safe-password")

    def test_empty_secret_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "secret"
            secret.write_text("\n", encoding="utf-8")
            with patch.dict(
                os.environ, {"ADMIN_PASSWORD_FILE": str(secret)}, clear=True
            ):
                with self.assertRaises(SettingsError):
                    build_updates()

    def test_empty_direct_secret_is_treated_as_unset(self) -> None:
        with patch.dict(os.environ, {"ADMIN_PASSWORD": ""}, clear=True):
            updates, _ = build_updates()
        self.assertNotIn("AdminPassword", updates.get("ServerSetting", {}))

    def test_empty_non_secret_setting_is_treated_as_unset(self) -> None:
        with patch.dict(os.environ, {"MAX_PLAYERS": ""}, clear=True):
            updates, _ = build_updates()
        self.assertNotIn("MaxPlayers", updates.get("ServerSetting", {}))

    def test_whitespace_direct_secret_is_rejected(self) -> None:
        with patch.dict(os.environ, {"ADMIN_PASSWORD": "   "}, clear=True):
            with self.assertRaises(SettingsError):
                build_updates()

    def test_first_creation_requires_password_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "REQUIRE_PASSWORD": "true",
                },
                clear=True,
            ):
                settings = Settings.from_env()
                with self.assertRaises(SettingsError):
                    apply_configuration(settings)

    def test_existing_config_without_overrides_gets_no_empty_server_section(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {"DATA_DIR": directory, "RUNTIME_DIR": f"{directory}/runtime"},
                clear=True,
            ):
                settings = Settings.from_env()
                settings.game_ini.parent.mkdir(parents=True)
                settings.game_ini.write_text("[Other]\nValue=1\n", encoding="utf-8")
                apply_configuration(settings)
                content = settings.game_ini.read_text(encoding="utf-8")
        self.assertNotIn("[ServerSetting]", content)

    def test_invalid_player_count(self) -> None:
        with patch.dict(os.environ, {"MAX_PLAYERS": "100"}, clear=True):
            with self.assertRaises(SettingsError):
                build_updates()

    def test_rejects_multiline_value(self) -> None:
        with patch.dict(os.environ, {"SERVER_NAME": "good\nInjected=bad"}, clear=True):
            with self.assertRaises(SettingsError):
                build_updates()

    def test_rejects_invalid_json_key(self) -> None:
        with patch.dict(
            os.environ,
            {"GAME_INI_OVERRIDES": '{"ServerSetting":{"Bad\nKey":"value"}}'},
            clear=True,
        ):
            with self.assertRaises(SettingsError):
                build_updates()

    def test_rejects_non_finite_json_override(self) -> None:
        for value in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.subTest(value=value):
                override = f'{{"Future":{{"Setting":{value}}}}}'
                with patch.dict(
                    os.environ, {"GAME_INI_OVERRIDES": override}, clear=True
                ):
                    with self.assertRaisesRegex(SettingsError, "must be finite"):
                        build_updates()


if __name__ == "__main__":
    unittest.main()
