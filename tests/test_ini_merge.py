from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nos_server.ini_merge import merge_ini


class IniMergeTests(unittest.TestCase):
    def test_preserves_comments_unknown_keys_and_updates_selected_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Game.ini"
            path.write_text(
                "; top comment\n[ServerSetting]\nServerName=Old\nUnknown=Keep\n\n[GameSettings]\nPVP=False\n",
                encoding="utf-8",
            )
            merge_ini(
                path,
                {
                    "ServerSetting": {"ServerName": "New", "MaxPlayers": "8"},
                    "GameSettings": {"PVP": "True"},
                    "FutureSection": {"FutureKey": "FutureValue"},
                },
            )
            result = path.read_text(encoding="utf-8")
            self.assertIn("; top comment", result)
            self.assertIn("ServerName=New", result)
            self.assertIn("Unknown=Keep", result)
            self.assertIn("MaxPlayers=8", result)
            self.assertIn("PVP=True", result)
            self.assertIn("[FutureSection]", result)
            self.assertIn("FutureKey=FutureValue", result)

    def test_uses_template_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template.ini"
            target = root / "nested" / "Game.ini"
            template.write_text(
                "[ServerSetting]\nServerName=Template\n", encoding="utf-8"
            )
            merge_ini(target, {"ServerSetting": {"ServerName": "Configured"}}, template)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                "[ServerSetting]\nServerName=Configured\n",
            )

    def test_case_variant_sections_are_merged_instead_of_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Game.ini"
            merge_ini(
                path,
                {
                    "ServerSetting": {"Password": "secret", "AdminPassword": "admin"},
                    "serversetting": {"FutureSetting": "enabled"},
                },
            )
            result = path.read_text(encoding="utf-8")
        self.assertIn("[ServerSetting]", result)
        self.assertIn("Password=secret", result)
        self.assertIn("AdminPassword=admin", result)
        self.assertIn("FutureSetting=enabled", result)
        self.assertNotIn("[serversetting]", result)


if __name__ == "__main__":
    unittest.main()
