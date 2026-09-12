from __future__ import annotations

import unittest
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LocalCiRetryTests(unittest.TestCase):
    def test_shell_gate_fails_on_an_earlier_script_syntax_error(self) -> None:
        make = shutil.which("make")
        if make is None:
            self.skipTest("make is not installed")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copyfile(ROOT / "Makefile", root / "Makefile")
            (root / "scripts").mkdir()
            (root / "docker-entrypoint.sh").write_text("true\n")
            (root / "scripts/a-bad.sh").write_text("if then\n")
            (root / "scripts/z-good.sh").write_text("true\n")
            later_check = root / "scripts/test-shell-behavior.sh"
            later_check.write_text("#!/bin/sh\ntouch incorrectly-passed\n")
            later_check.chmod(0o755)
            result = subprocess.run(
                [make, "shell-check"], cwd=root, capture_output=True, timeout=10
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "incorrectly-passed").exists())

    def test_integration_ports_are_published_only_on_loopback(self) -> None:
        linux = (ROOT / "scripts/integration-test.sh").read_text(encoding="utf-8")
        windows = (ROOT / "scripts/run-local-ci.ps1").read_text(encoding="utf-8")
        self.assertIn("-p 127.0.0.1:17777:7777/udp", linux)
        self.assertIn("-p 127.0.0.1:37015:27015/udp", linux)
        self.assertIn('"-p", "127.0.0.1:${gamePort}:7777/udp"', windows)
        self.assertIn('"-p", "127.0.0.1:${queryPort}:27015/udp"', windows)

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
