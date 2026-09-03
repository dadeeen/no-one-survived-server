from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

HEARTBEAT_WRITE_INTERVAL_SECONDS = 5.0


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        now = time.time()
        self._data: dict[str, Any] = {
            "state": "INITIALIZING",
            "state_since": now,
            "heartbeat": now,
            "pid": None,
            "players": None,
            "ready": False,
            "last_error": None,
            "wake_source": None,
            "a2s_ok": None,
            "a2s_error": None,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_locked()

    def _write_locked(self) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp"
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = -1
                handle.write(json.dumps(self._data, indent=2, sort_keys=True) + "\n")
                handle.flush()
            os.replace(temporary, self.path)
        except BaseException:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)
            raise

    def set_state(self, state: str, **values: Any) -> None:
        with self._lock:
            now = time.time()
            changed = False
            if self._data.get("state") != state:
                self._data["state"] = state
                self._data["state_since"] = now
                changed = True
            if state == "STARTING":
                if self._data.get("a2s_ok") is not None:
                    self._data["a2s_ok"] = None
                    changed = True
                if self._data.get("a2s_error") is not None:
                    self._data["a2s_error"] = None
                    changed = True
            if state != "ERROR":
                for key in ("retry_in_seconds", "startup_retry_attempt"):
                    if key in self._data:
                        self._data.pop(key)
                        changed = True
            for key, value in values.items():
                if key not in self._data or self._data[key] != value:
                    self._data[key] = value
                    changed = True
            if (
                changed
                or now - float(self._data.get("heartbeat", 0))
                >= HEARTBEAT_WRITE_INTERVAL_SECONDS
            ):
                self._data["heartbeat"] = now
                self._write_locked()

    def update(self, **values: Any) -> None:
        with self._lock:
            now = time.time()
            changed = False
            for key, value in values.items():
                if key not in self._data or self._data[key] != value:
                    self._data[key] = value
                    changed = True
            if (
                changed
                or now - float(self._data.get("heartbeat", 0))
                >= HEARTBEAT_WRITE_INTERVAL_SECONDS
            ):
                self._data["heartbeat"] = now
                self._write_locked()

    def touch(self, minimum_interval: float = HEARTBEAT_WRITE_INTERVAL_SECONDS) -> None:
        with self._lock:
            now = time.time()
            if now - float(self._data.get("heartbeat", 0)) < minimum_interval:
                return
            self._data["heartbeat"] = now
            self._write_locked()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)
