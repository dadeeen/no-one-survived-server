from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nos_server.configuration import apply_configuration, build_updates
from nos_server.settings import Settings, SettingsError


class ConfigurationTests(unittest.TestCase):
    def test_material_amount_accepts_only_the_four_integer_choices(self) -> None:
        for value in ("0", "1", "2", "3"):
            with (
                self.subTest(value=value),
                patch.dict(os.environ, {"MATERIAL_AMOUNT": value}, clear=True),
            ):
                updates, _ = build_updates()
                self.assertEqual(updates["GameSettings"]["MaterialNum"], value)
        for value in ("-1", "4", "1.5", "nan"):
            with (
                self.subTest(value=value),
                patch.dict(os.environ, {"MATERIAL_AMOUNT": value}, clear=True),
            ):
                with self.assertRaises(SettingsError):
                    build_updates()

    def test_respawn_intervals_are_integer_days_with_individual_minimums(self) -> None:
        for variable, key, minimum in (
            ("ITEM_SPAWN", "ItemSpawn", 0),
            ("NPC_ITEM_SPAWN", "NPCItemSpawn", 1),
        ):
            for value in (str(minimum), "15", "365"):
                with (
                    self.subTest(variable=variable, value=value),
                    patch.dict(os.environ, {variable: value}, clear=True),
                ):
                    updates, _ = build_updates()
                    self.assertEqual(updates["GameSettings"][key], value)
            for value in (str(minimum - 1), "0.5", "inf"):
                with (
                    self.subTest(variable=variable, value=value),
                    patch.dict(os.environ, {variable: value}, clear=True),
                ):
                    with self.assertRaises(SettingsError):
                        build_updates()

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

    def test_json_keys_cannot_insert_sections_or_comments(self) -> None:
        for key in (
            "[ServerSetting] #",
            " [ServerSetting] ;",
            ";Ignored",
            " #Ignored",
            " \t",
        ):
            with self.subTest(key=key):
                overrides = {"Future": {key: "", "Password": "shadow"}}
                with patch.dict(
                    os.environ,
                    {"GAME_INI_OVERRIDES": json.dumps(overrides)},
                    clear=True,
                ):
                    with self.assertRaisesRegex(SettingsError, "Invalid INI key"):
                        build_updates()

    def test_rejects_blank_json_section(self) -> None:
        with patch.dict(
            os.environ, {"GAME_INI_OVERRIDES": '{" ":{"Setting":1}}'}, clear=True
        ):
            with self.assertRaisesRegex(SettingsError, "Invalid INI section"):
                build_updates()

    def test_invalid_json_names_are_not_exposed_in_errors(self) -> None:
        for overrides in (
            {"private-section\n": {"Setting": 1}},
            {"Future": {"private-key\n": 1}},
        ):
            with self.subTest(overrides=overrides):
                with patch.dict(
                    os.environ,
                    {"GAME_INI_OVERRIDES": json.dumps(overrides)},
                    clear=True,
                ):
                    with self.assertRaises(SettingsError) as raised:
                        build_updates()
                self.assertNotIn("private-", str(raised.exception))

    def test_rejects_non_finite_json_override(self) -> None:
        for value in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.subTest(value=value):
                override = f'{{"Future":{{"Setting":{value}}}}}'
                with patch.dict(
                    os.environ, {"GAME_INI_OVERRIDES": override}, clear=True
                ):
                    with self.assertRaisesRegex(SettingsError, "must be finite"):
                        build_updates()

    def test_rejects_case_insensitive_override_of_managed_key(self) -> None:
        with patch.dict(
            os.environ,
            {"GAME_INI_OVERRIDES": '{"serversetting":{"password":"shadow"}}'},
            clear=True,
        ):
            with self.assertRaisesRegex(SettingsError, "managed setting"):
                build_updates()

    def test_rejects_operator_prefixed_managed_keys(self) -> None:
        for operator in ("+", ".", "-", "!"):
            for key in ("Password", " pAsSwOrD ", "AdminPassword"):
                with self.subTest(operator=operator, key=key):
                    overrides = {" sErVeRsEtTiNg ": {f" {operator}{key} ": "shadow"}}
                    with patch.dict(
                        os.environ,
                        {"GAME_INI_OVERRIDES": json.dumps(overrides)},
                        clear=True,
                    ):
                        with self.assertRaisesRegex(SettingsError, "managed setting"):
                            build_updates()

    def test_unmanaged_array_operators_are_preserved(self) -> None:
        overrides = {
            "Future": {
                "!MyArray": "ClearArray",
                "+MyArray": "first",
                ".MyArray": "first",
                "-MyArray": "second",
            }
        }
        with patch.dict(
            os.environ,
            {"GAME_INI_OVERRIDES": json.dumps(overrides)},
            clear=True,
        ):
            updates, _ = build_updates()
        self.assertEqual(updates, overrides)

    def test_case_variant_section_with_unmanaged_key_keeps_managed_secrets(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {
                    "DATA_DIR": directory,
                    "RUNTIME_DIR": f"{directory}/runtime",
                    "REQUIRE_PASSWORD": "true",
                    "SERVER_PASSWORD": "letmein",
                    "GAME_INI_OVERRIDES": (
                        '{"serversetting":{"FutureSetting":"enabled"}}'
                    ),
                },
                clear=True,
            ):
                settings = Settings.from_env()
                apply_configuration(settings)
                content = settings.game_ini.read_text(encoding="utf-8")
        self.assertIn("NeedPassword=True", content)
        self.assertIn("Password=letmein", content)
        self.assertIn("AdminPassword=", content)
        self.assertIn("FutureSetting=enabled", content)


if __name__ == "__main__":
    unittest.main()
