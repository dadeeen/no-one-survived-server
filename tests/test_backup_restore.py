from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "POSIX backup helpers required")
class BackupRestoreTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("run backup tests as an unprivileged user")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.data = Path(self.temporary.name)
        self.saved = self.data / "saved"
        self.saved.mkdir()
        (self.saved / "world.sav").write_bytes(b"original")
        self.env = os.environ | {
            "DATA_DIR": str(self.data),
            "SAVED_DIR": str(self.saved),
            "BACKUP_DIR": str(self.data / "backups"),
            "KEEP_BACKUPS": "1",
        }

    def run_helper(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / name), *args],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def create_backup(self) -> Path:
        result = self.run_helper("backup.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        return next((self.data / "backups").glob("saved-*.tar.gz"))

    def test_hardlinked_files_can_be_restored(self) -> None:
        os.link(self.saved / "world.sav", self.saved / "copy.sav")
        archive = self.create_backup()
        (self.saved / "world.sav").write_bytes(b"changed")

        result = self.run_helper("restore.sh", str(archive))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.saved / "world.sav").read_bytes(), b"original")
        self.assertEqual((self.saved / "copy.sav").read_bytes(), b"original")

    def test_restore_accepts_zero_prefixed_decimal_ids(self) -> None:
        archive = self.create_backup()
        self.env.update(PUID="08", PGID="09")

        result = self.run_helper("restore.sh", str(archive))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.saved / "world.sav").read_bytes(), b"original")

    def test_unsupported_files_do_not_replace_valid_backups(self) -> None:
        archive = self.create_backup()
        original = archive.read_bytes()
        entry = self.saved / "unsupported"
        for kind in ("symlink", "fifo"):
            with self.subTest(kind=kind):
                if kind == "symlink":
                    entry.symlink_to(self.saved / "world.sav")
                else:
                    os.mkfifo(entry)
                result = self.run_helper("backup.sh")
                entry.unlink()

                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Created", result.stdout)
                self.assertEqual(list(archive.parent.glob("*.tar.gz")), [archive])
                self.assertEqual(archive.read_bytes(), original)

    def test_interrupt_during_restore_restores_previous_directory(self) -> None:
        archive = self.create_backup()
        fake_bin = self.data / "bin"
        fake_bin.mkdir()
        move = shutil.which("mv")
        self.assertIsNotNone(move)
        wrapper = fake_bin / "mv"
        wrapper.write_text(
            "#!/usr/bin/env bash\nset -eu\n"
            f'{shlex.quote(str(move))} "$@"\n'
            'if [[ "$3" == "$SAVED_DIR" ]]; then\n'
            '  kill -"$TEST_RESTORE_SIGNAL" "$PPID"\n'
            "fi\n"
        )
        wrapper.chmod(0o755)
        self.env["PATH"] = str(fake_bin) + os.pathsep + self.env["PATH"]
        (self.saved / "world.sav").write_bytes(b"current")

        for signal_name, exit_code in (("HUP", 129), ("INT", 130), ("TERM", 143)):
            with self.subTest(signal=signal_name):
                self.env["TEST_RESTORE_SIGNAL"] = signal_name
                result = self.run_helper("restore.sh", str(archive))

                self.assertEqual(result.returncode, exit_code, result.stderr)
                self.assertEqual((self.saved / "world.sav").read_bytes(), b"current")
                self.assertEqual(list(self.data.glob(".restore-stage.*")), [])
                self.assertEqual(list(self.data.glob("saved.before-restore.*")), [])

    def test_failed_swap_restores_previous_directory(self) -> None:
        archive = self.create_backup()
        fake_bin = self.data / "bin"
        fake_bin.mkdir()
        move = shutil.which("mv")
        self.assertIsNotNone(move)
        wrapper = fake_bin / "mv"
        wrapper.write_text(
            "#!/usr/bin/env bash\nset -eu\n"
            'if [[ "$3" == */.restore-stage.*/saved ]]; then exit 1; fi\n'
            f'exec {shlex.quote(str(move))} "$@"\n'
        )
        wrapper.chmod(0o755)
        self.env["PATH"] = str(fake_bin) + os.pathsep + self.env["PATH"]
        (self.saved / "world.sav").write_bytes(b"current")

        result = self.run_helper("restore.sh", str(archive))

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("restore swap failed", result.stderr)
        self.assertEqual((self.saved / "world.sav").read_bytes(), b"current")
        self.assertEqual(list(self.data.glob(".restore-stage.*")), [])
        self.assertEqual(list(self.data.glob("saved.before-restore.*")), [])

    def test_failed_rollback_retains_previous_save_data(self) -> None:
        archive = self.create_backup()
        fake_bin = self.data / "bin"
        fake_bin.mkdir()
        move = shutil.which("mv")
        self.assertIsNotNone(move)
        wrapper = fake_bin / "mv"
        wrapper.write_text(
            "#!/usr/bin/env bash\nset -eu\n"
            'if [[ "$4" == "$SAVED_DIR" ]]; then exit 1; fi\n'
            f'exec {shlex.quote(str(move))} "$@"\n'
        )
        wrapper.chmod(0o755)
        self.env["PATH"] = str(fake_bin) + os.pathsep + self.env["PATH"]
        (self.saved / "world.sav").write_bytes(b"current")

        result = self.run_helper("restore.sh", str(archive))

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("restore rollback failed", result.stderr)
        retained = list(self.data.glob("saved.before-restore.*"))
        self.assertEqual(len(retained), 1)
        self.assertIn(str(retained[0]), result.stderr)
        self.assertEqual((retained[0] / "world.sav").read_bytes(), b"current")
        self.assertFalse(self.saved.exists())
        self.assertEqual(list(self.data.glob(".restore-stage.*")), [])


if __name__ == "__main__":
    unittest.main()
