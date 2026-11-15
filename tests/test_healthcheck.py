from __future__ import annotations

import io
import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from nos_server import healthcheck


class HealthcheckTests(unittest.TestCase):
    def test_rejects_inactive_or_unknown_state(self) -> None:
        states = (
            {},
            {"state": "STOPPED"},
            {"state": "ERROR"},
            {"state": "unknown"},
            {"state": None},
            {"state": []},
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            for state in states:
                with self.subTest(state=state):
                    path.write_text(
                        json.dumps({**state, "heartbeat": time.time()}),
                        encoding="utf-8",
                    )
                    with (
                        patch.dict(os.environ, {"STATE_FILE": str(path)}, clear=True),
                        redirect_stdout(io.StringIO()),
                    ):
                        self.assertEqual(healthcheck.main(), 1)

    def test_accepts_each_active_supervisor_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            for state in (
                "INITIALIZING",
                "PREPARING",
                "UPDATING",
                "SLEEPING",
                "STARTING",
                "RUNNING",
                "IDLE",
                "STOPPING",
            ):
                with self.subTest(state=state):
                    path.write_text(
                        json.dumps({"state": state, "heartbeat": time.time()}),
                        encoding="utf-8",
                    )
                    with (
                        patch.dict(os.environ, {"STATE_FILE": str(path)}, clear=True),
                        redirect_stdout(io.StringIO()),
                    ):
                        self.assertEqual(healthcheck.main(), 0)

    def test_rejects_invalid_utf8_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_bytes(b"\xff\n")
            output = io.StringIO()
            with (
                patch.dict(os.environ, {"STATE_FILE": str(path)}, clear=True),
                redirect_stdout(output),
            ):
                self.assertEqual(healthcheck.main(), 1)
            self.assertIn("state unavailable", output.getvalue())

    def test_rejects_overflowing_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(
                json.dumps({"state": "SLEEPING", "heartbeat": 10**400}),
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                patch.dict(os.environ, {"STATE_FILE": str(path)}, clear=True),
                redirect_stdout(output),
            ):
                self.assertEqual(healthcheck.main(), 1)
            self.assertIn(
                "invalid health-check configuration or state", output.getvalue()
            )

    def test_rejects_non_object_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("[]\n", encoding="utf-8")
            output = io.StringIO()
            with (
                patch.dict(os.environ, {"STATE_FILE": str(path)}, clear=True),
                redirect_stdout(output),
            ):
                result = healthcheck.main()
        self.assertEqual(result, 1)
        self.assertIn("expected a JSON object", output.getvalue())

    def test_rejects_non_finite_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(
                json.dumps({"state": "SLEEPING", "heartbeat": float("nan")}) + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                patch.dict(os.environ, {"STATE_FILE": str(path)}, clear=True),
                redirect_stdout(output),
            ):
                result = healthcheck.main()
        self.assertEqual(result, 1)
        self.assertIn("heartbeat must be finite", output.getvalue())

    def test_rejects_heartbeat_far_in_the_future(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(
                json.dumps({"state": "SLEEPING", "heartbeat": time.time() + 3600})
                + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                patch.dict(
                    os.environ,
                    {
                        "STATE_FILE": str(path),
                        "HEALTHCHECK_MAX_HEARTBEAT_AGE": "600",
                    },
                    clear=True,
                ),
                redirect_stdout(output),
            ):
                result = healthcheck.main()
        self.assertEqual(result, 1)
        self.assertIn("in the future", output.getvalue())

    def test_accepts_recent_sleeping_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(
                json.dumps({"state": "SLEEPING", "heartbeat": time.time()}) + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                patch.dict(os.environ, {"STATE_FILE": str(path)}, clear=True),
                redirect_stdout(output),
            ):
                result = healthcheck.main()
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
