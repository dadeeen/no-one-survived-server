from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "POSIX backup helper required")
class BackupRetentionTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("run backup tests as an unprivileged user")

    def run_backup(self, count: str) -> tuple[subprocess.CompletedProcess[str], int]:
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            saved = data / "saved"
            saved.mkdir()
            (saved / "world.sav").write_bytes(b"save data")
            backups = data / "backups"
            backups.mkdir()
            for number in range(12):
                archive = backups / f"saved-{number:02d}.tar.gz"
                archive.touch()
                os.utime(archive, (number + 1, number + 1))
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "DATA_DIR": str(data),
                "KEEP_BACKUPS": count,
            }
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/backup.sh")],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result, len(list(backups.glob("saved-*.tar.gz")))

    def test_zero_prefixed_limits_are_decimal(self) -> None:
        for value, expected in (("08", 8), ("010", 10), ("000", 13)):
            with self.subTest(value=value):
                result, remaining = self.run_backup(value)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(remaining, expected)

    def test_overflow_is_rejected_before_writing(self) -> None:
        for value in ("9223372036854775807", "18446744073709551617"):
            with self.subTest(value=value):
                result, remaining = self.run_backup(value)
                self.assertEqual(result.returncode, 2)
                self.assertIn("KEEP_BACKUPS is too large", result.stderr)
                self.assertEqual(remaining, 12)


if __name__ == "__main__":
    unittest.main()
