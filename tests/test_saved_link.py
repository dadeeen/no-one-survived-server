from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from nos_server.settings import Settings
from nos_server.steamcmd import ensure_saved_link


class SavedLinkTests(unittest.TestCase):
    def test_failed_migration_can_retry_without_publishing_partial_save(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"DATA_DIR": directory}, clear=True),
        ):
            settings = Settings.from_env()
            original = settings.server_saved_path
            original.mkdir(parents=True)
            (original / "world.sav").write_text("world")
            (original / "players.sav").write_text("players")

            def partial_copy(source, destination):
                destination.mkdir()
                (destination / "world.sav").write_text("partial")
                raise OSError("disk full")

            with patch("nos_server.steamcmd._copy_contents", side_effect=partial_copy):
                with self.assertRaisesRegex(OSError, "disk full"):
                    ensure_saved_link(settings)
            self.assertEqual(list(settings.saved_dir.iterdir()), [])
            self.assertFalse(original.is_symlink())
            ensure_saved_link(settings)
            self.assertTrue(original.is_symlink())
            self.assertEqual((settings.saved_dir / "world.sav").read_text(), "world")
            self.assertEqual((settings.saved_dir / "players.sav").read_text(), "players")

    def test_migrates_existing_server_saved_directory(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"DATA_DIR": directory}, clear=True),
        ):
            settings = Settings.from_env()
            old_saved = settings.server_saved_path
            old_saved.mkdir(parents=True)
            (old_saved / "world.sav").write_text("save", encoding="utf-8")
            ensure_saved_link(settings)
            self.assertTrue(old_saved.is_symlink())
            self.assertEqual(
                (settings.saved_dir / "world.sav").read_text(encoding="utf-8"),
                "save",
            )

    def test_moves_conflicting_directory_aside(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"DATA_DIR": directory}, clear=True),
        ):
            settings = Settings.from_env()
            settings.saved_dir.mkdir(parents=True)
            (settings.saved_dir / "persistent.sav").write_text("keep", encoding="utf-8")
            old_saved = settings.server_saved_path
            old_saved.mkdir(parents=True)
            (old_saved / "unexpected.sav").write_text("orphan", encoding="utf-8")
            ensure_saved_link(settings)
            self.assertTrue(old_saved.is_symlink())
            orphans = list(settings.state_dir.glob("orphaned-server-saved-*"))
            self.assertEqual(len(orphans), 1)
            self.assertTrue((orphans[0] / "unexpected.sav").exists())


if __name__ == "__main__":
    unittest.main()
