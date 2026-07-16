from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LocalCiRetryTests(unittest.TestCase):
    def test_integration_container_uses_short_update_retry_delay(self) -> None:
        local_runner = (ROOT / "scripts/run-local-ci.ps1").read_text(encoding="utf-8")
        override = '"-e", "UPDATE_RETRY_DELAY_SECONDS=30"'
        integration_start = local_runner.index("if ($runIntegration) {")
        run_start = local_runner.index('"run", "-d",', integration_start)
        run_end = local_runner.index("\n        )", run_start)
        integration_run = local_runner[run_start:run_end]

        self.assertEqual(local_runner.count(override), 1)
        self.assertLess(
            integration_run.index('"-e", "PREPARE_ON_CONTAINER_START=true"'),
            integration_run.index(override),
        )
        self.assertLess(
            integration_run.index(override),
            integration_run.index('"nos-integration:local"'),
        )


if __name__ == "__main__":
    unittest.main()
