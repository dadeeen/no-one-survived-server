from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable


class OperationCancelled(RuntimeError):
    """A shutdown interrupted a preparation operation."""


def check_cancelled(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise OperationCancelled("Preparation cancelled by shutdown")


def wait_process(
    process: subprocess.Popen[str],
    timeout: float,
    heartbeat: Callable[[], None] | None,
    cancel: threading.Event | None,
) -> int:
    deadline = time.monotonic() + timeout
    while True:
        check_cancelled(cancel)
        if heartbeat:
            heartbeat()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, timeout)
        try:
            return process.wait(timeout=min(1.0, remaining))
        except subprocess.TimeoutExpired:
            continue
