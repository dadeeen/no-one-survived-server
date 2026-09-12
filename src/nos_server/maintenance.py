from __future__ import annotations

import fcntl
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .operations import OperationCancelled


class DataLock:
    """One advisory lock for the supervisor and save maintenance helpers.

    The file stays outside any directory that a restore or update replaces.
    It must never be unlinked while this data volume is in use.
    """

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / ".nos-maintenance.lock"
        self._fd: int | None = None
        self._depth = 0

    def try_acquire(self) -> bool:
        if self._fd is not None:
            self._depth += 1
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(descriptor)
            return False
        except BaseException:
            os.close(descriptor)
            raise
        self._fd = descriptor
        self._depth = 1
        return True

    def release(self) -> None:
        if self._fd is None:
            return
        self._depth -= 1
        if self._depth == 0:
            os.close(self._fd)
            self._fd = None

    @contextmanager
    def hold(
        self, cancel: threading.Event, heartbeat: Callable[[], None]
    ) -> Iterator[None]:
        while not self.try_acquire():
            heartbeat()
            if cancel.wait(0.25):
                raise OperationCancelled("Shutdown while waiting for save maintenance")
        try:
            if cancel.is_set():
                raise OperationCancelled("Shutdown before data access")
            yield
        finally:
            self.release()
