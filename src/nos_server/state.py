from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any


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
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, self.path)

    def set_state(self, state: str, **values: Any) -> None:
        with self._lock:
            if self._data.get("state") != state:
                self._data["state"] = state
                self._data["state_since"] = time.time()
            if state == "STARTING":
                self._data["a2s_ok"] = None
                self._data["a2s_error"] = None
            if state != "ERROR":
                self._data.pop("retry_in_seconds", None)
                self._data.pop("startup_retry_attempt", None)
            self._data.update(values)
            self._data["heartbeat"] = time.time()
            self._write_locked()

    def update(self, **values: Any) -> None:
        with self._lock:
            self._data.update(values)
            self._data["heartbeat"] = time.time()
            self._write_locked()

    def touch(self, minimum_interval: float = 5.0) -> None:
        with self._lock:
            now = time.time()
            if now - float(self._data.get("heartbeat", 0)) < minimum_interval:
                return
            self._data["heartbeat"] = now
            self._write_locked()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)
