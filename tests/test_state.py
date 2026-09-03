from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nos_server.state import StateStore


class StateStoreTests(unittest.TestCase):
    def test_a2s_fields_exist_before_first_query_and_reset_on_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = StateStore(Path(directory) / "state.json")
            initial = state.snapshot()
            state.update(a2s_ok=True, a2s_error="stale failure")
            state.set_state("STARTING")
            starting = state.snapshot()
        self.assertIn("a2s_ok", initial)
        self.assertIn("a2s_error", initial)
        self.assertIsNone(initial["a2s_ok"])
        self.assertIsNone(initial["a2s_error"])
        self.assertIsNone(starting["a2s_ok"])
        self.assertIsNone(starting["a2s_error"])

    def test_retry_metadata_is_removed_after_leaving_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = StateStore(Path(directory) / "state.json")
            state.set_state(
                "ERROR",
                last_error="temporary failure",
                retry_in_seconds=30,
                startup_retry_attempt=2,
            )
            state.set_state("SLEEPING", last_error=None)
            snapshot = state.snapshot()
        self.assertEqual(snapshot["state"], "SLEEPING")
        self.assertNotIn("retry_in_seconds", snapshot)
        self.assertNotIn("startup_retry_attempt", snapshot)

    def test_unchanged_state_updates_do_not_rewrite_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = StateStore(Path(directory) / "state.json")
            with patch.object(
                state, "_write_locked", wraps=state._write_locked
            ) as write:
                state.set_state("RUNNING", ready=True)
                state.set_state("RUNNING", ready=True)
                state.update(ready=True)
        self.assertEqual(write.call_count, 1)

    def test_temp_file_is_private_and_keeps_full_state_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custom.state.json"
            old_umask = os.umask(0)
            try:
                with patch("nos_server.state.os.replace", wraps=os.replace) as replace:
                    StateStore(path)
            finally:
                os.umask(old_umask)
            temporary = Path(replace.call_args.args[0])
            mode = path.stat().st_mode & 0o777
        self.assertTrue(temporary.name.startswith(".custom.state.json."))
        self.assertTrue(temporary.name.endswith(".tmp"))
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()
