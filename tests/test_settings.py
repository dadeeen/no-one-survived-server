from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from nos_server.settings import Settings, SettingsError


class SettingsTests(unittest.TestCase):
    def test_wake_can_be_disabled_for_manual_control(self) -> None:
        with patch.dict(
            os.environ,
            {"WAKE_ON_GAME_PORT": "false", "WAKE_ON_QUERY_PORT": "false"},
            clear=True,
        ):
            settings = Settings.from_env()
        self.assertFalse(settings.wake_on_game_port)
        self.assertFalse(settings.wake_on_query_port)

    def test_default_wake_source_policy_is_private(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.wake_source_policy, "private")

    def test_xvfb_is_default_but_can_be_disabled(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
        self.assertTrue(settings.use_xvfb)
        with patch.dict(os.environ, {"USE_XVFB": "false"}, clear=True):
            settings = Settings.from_env()
        self.assertFalse(settings.use_xvfb)

    def test_rejects_unknown_wake_source_policy(self) -> None:
        with patch.dict(os.environ, {"WAKE_SOURCE_POLICY": "internet"}, clear=True):
            with self.assertRaises(SettingsError):
                Settings.from_env()

    def test_allowlist_policy_requires_networks(self) -> None:
        with patch.dict(os.environ, {"WAKE_SOURCE_POLICY": "allowlist"}, clear=True):
            with self.assertRaises(SettingsError):
                Settings.from_env()

    def test_allowlist_policy_accepts_networks(self) -> None:
        with patch.dict(
            os.environ,
            {
                "WAKE_SOURCE_POLICY": "allowlist",
                "WAKE_ALLOWED_NETWORKS": "192.168.10.0/24",
            },
            clear=True,
        ):
            settings = Settings.from_env()
        self.assertEqual(settings.wake_source_policy, "allowlist")
        self.assertEqual(settings.wake_allowed_networks, ("192.168.10.0/24",))

    def test_update_and_wine_timeouts_are_configurable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "UPDATE_RETRY_DELAY_SECONDS": "120",
                "STEAMCMD_TIMEOUT_SECONDS": "7200",
                "WINEBOOT_TIMEOUT_SECONDS": "900",
            },
            clear=True,
        ):
            settings = Settings.from_env()
        self.assertEqual(settings.update_retry_delay_seconds, 120)
        self.assertEqual(settings.steamcmd_timeout_seconds, 7200)
        self.assertEqual(settings.wineboot_timeout_seconds, 900)

    def test_rejects_non_finite_a2s_timeout(self) -> None:
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"A2S_TIMEOUT_SECONDS": value}, clear=True):
                    with self.assertRaises(SettingsError):
                        Settings.from_env()

    def test_blank_a2s_host_uses_multihome_default(self) -> None:
        with patch.dict(
            os.environ,
            {"MULTIHOME": "192.0.2.10", "A2S_QUERY_HOST": ""},
            clear=True,
        ):
            settings = Settings.from_env()
        self.assertEqual(settings.a2s_query_host, "192.0.2.10")

    def test_runtime_paths_follow_runtime_dir(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RUNTIME_DIR": "/tmp/nos-runtime",
                "STATE_FILE": "",
                "CONTROL_SOCKET": "",
            },
            clear=True,
        ):
            settings = Settings.from_env()
        self.assertEqual(settings.state_file, Path("/tmp/nos-runtime/state.json"))
        self.assertEqual(settings.control_socket, Path("/tmp/nos-runtime/control.sock"))

    def test_runtime_endpoint_overrides_are_honored(self) -> None:
        with patch.dict(
            os.environ,
            {
                "STATE_FILE": "/tmp/custom-state.json",
                "CONTROL_SOCKET": "/tmp/custom-control.sock",
            },
            clear=True,
        ):
            settings = Settings.from_env()
        self.assertEqual(settings.state_file, Path("/tmp/custom-state.json"))
        self.assertEqual(settings.control_socket, Path("/tmp/custom-control.sock"))

    def test_rejects_relative_paths_before_resolution(self) -> None:
        for name, value in (
            ("DATA_DIR", "data"),
            ("RUNTIME_DIR", "runtime"),
            ("SERVER_DIR", "server"),
            ("STATE_FILE", "state.json"),
            ("CONTROL_SOCKET", "control.sock"),
        ):
            with self.subTest(name=name):
                with patch.dict(os.environ, {name: value}, clear=True):
                    with self.assertRaises(SettingsError):
                        Settings.from_env()

    def test_ports_must_differ(self) -> None:
        with patch.dict(
            os.environ, {"GAME_PORT": "7777", "QUERY_PORT": "7777"}, clear=True
        ):
            with self.assertRaises(SettingsError):
                Settings.from_env()

    def test_rejects_ipv6_wake_network(self) -> None:
        with patch.dict(os.environ, {"WAKE_ALLOWED_NETWORKS": "fd00::/8"}, clear=True):
            with self.assertRaises(SettingsError):
                Settings.from_env()

    def test_rejects_persistent_path_outside_data(self) -> None:
        with patch.dict(
            os.environ,
            {"DATA_DIR": "/data", "WINEPREFIX": "/tmp/unsafe-wine"},
            clear=True,
        ):
            with self.assertRaises(SettingsError):
                Settings.from_env()


if __name__ == "__main__":
    unittest.main()
