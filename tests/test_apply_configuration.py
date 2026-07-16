from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nos_server.configuration import apply_configuration
from nos_server.settings import Settings


class ApplyConfigurationTests(unittest.TestCase):
    def test_generates_admin_password_and_updates_engine_ports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            game_template = root / "Game.template.ini"
            engine_template = root / "Engine.template.ini"
            game_template.write_text(
                "[ServerSetting]\nAdminPassword=\n", encoding="utf-8"
            )
            engine_template.write_text("[URL]\nPort=1\n", encoding="utf-8")
            env = {
                "DATA_DIR": str(root / "data"),
                "GAME_INI_TEMPLATE": str(game_template),
                "ENGINE_INI_TEMPLATE": str(engine_template),
                "GAME_PORT": "7778",
                "QUERY_PORT": "27016",
            }
            with patch.dict(os.environ, env, clear=True):
                settings = Settings.from_env()
                applied = apply_configuration(settings)
            self.assertTrue(any("generated" in item for item in applied))
            generated = settings.state_dir / "generated-admin-password"
            self.assertTrue(generated.exists())
            self.assertGreater(len(generated.read_text(encoding="utf-8").strip()), 20)
            engine = settings.engine_ini.read_text(encoding="utf-8")
            self.assertIn("Port=7778", engine)
            self.assertIn("GameServerQueryPort=27016", engine)


if __name__ == "__main__":
    unittest.main()
