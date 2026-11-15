from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SecurityWorkflowTests(unittest.TestCase):
    def test_scheduled_scan_checks_out_its_policy_script(self) -> None:
        workflow = (ROOT / ".github/workflows/security-scan.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("uses: actions/checkout@", workflow)
        self.assertLess(
            workflow.index("uses: actions/checkout@"),
            workflow.index("run: bash scripts/check-image-vulnerabilities.sh"),
        )


@unittest.skipUnless(shutil.which("bash") and shutil.which("jq"), "bash/jq required")
class ImageSecurityTests(unittest.TestCase):
    def run_report(self, report: object) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scan.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            return subprocess.run(
                ["bash", str(ROOT / "scripts/check-image-vulnerabilities.sh"), str(path)],
                capture_output=True,
                text=True,
                timeout=10,
            )

    @staticmethod
    def report(findings: object) -> dict[str, object]:
        return {
            "SchemaVersion": 2,
            "Results": [
                {
                    "Target": "image (debian 13)",
                    "Class": "os-pkgs",
                    "Type": "debian",
                    "Vulnerabilities": findings,
                }
            ],
        }

    def test_accepts_clean_reports(self) -> None:
        for findings in (None, []):
            with self.subTest(findings=findings):
                self.assertEqual(self.run_report(self.report(findings)).returncode, 0)

    def test_blocks_fixable_high_and_critical_findings(self) -> None:
        for severity in ("HIGH", "CRITICAL"):
            with self.subTest(severity=severity):
                result = self.run_report(
                    self.report(
                        [{"Severity": severity, "FixedVersion": "1.2.3"}]
                    )
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("gate passed", result.stdout)

    def test_keeps_unfixed_critical_findings_visible(self) -> None:
        result = self.run_report(self.report([{"Severity": "CRITICAL"}]))
        self.assertEqual(result.returncode, 0)
        self.assertIn("::warning::", result.stdout)
        self.assertIn("1 CRITICAL", result.stdout)

    def test_rejects_malformed_results(self) -> None:
        reports = (
            {},
            {"SchemaVersion": 2, "Results": []},
            {"SchemaVersion": 2, "Results": [None]},
            {"SchemaVersion": 2, "Results": [{}]},
            self.report("invalid"),
            self.report([None]),
            self.report([{}]),
            self.report([{"Severity": "critical", "FixedVersion": "1.2.3"}]),
            self.report([{"Severity": "HIGH", "FixedVersion": {}}]),
            self.report([{"Severity": "HIGH", "FixedVersion": 123}]),
        )
        for report in reports:
            with self.subTest(report=report):
                result = self.run_report(report)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("gate passed", result.stdout)

    def test_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    "bash",
                    str(ROOT / "scripts/check-image-vulnerabilities.sh"),
                    str(Path(directory) / "missing.json"),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
