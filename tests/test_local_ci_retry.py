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

    def test_linux_integration_waits_through_retryable_error(self) -> None:
        integration = (ROOT / "scripts/integration-test.sh").read_text(encoding="utf-8")
        self.assertIn('get("retry_in_seconds")', integration)
        self.assertIn('if [[ -z "$retry_in" ]]', integration)
        self.assertIn("entered terminal ERROR", integration)


if __name__ == "__main__":
    unittest.main()
