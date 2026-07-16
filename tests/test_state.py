from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
