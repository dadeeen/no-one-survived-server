from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any


def main() -> int:
    runtime_dir = Path(os.getenv("RUNTIME_DIR", "/run/nos"))
    configured_state_file = os.getenv("STATE_FILE", "").strip()
    path = (
        Path(configured_state_file)
        if configured_state_file
        else runtime_dir / "state.json"
    )
    try:
        parsed: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"state unavailable: {exc}")
        return 1
    if not isinstance(parsed, dict):
        print("invalid health-check state: expected a JSON object")
        return 1
    state: dict[str, Any] = parsed
    if state.get("state") == "ERROR":
        print(state.get("last_error") or "supervisor error")
        return 1
    try:
        max_age = int(os.getenv("HEALTHCHECK_MAX_HEARTBEAT_AGE", "600"))
        heartbeat = float(state.get("heartbeat", 0))
    except (TypeError, ValueError) as exc:
        print(f"invalid health-check configuration or state: {exc}")
        return 1
    if max_age <= 0:
        print("HEALTHCHECK_MAX_HEARTBEAT_AGE must be positive")
        return 1
    if not math.isfinite(heartbeat):
        print("invalid health-check state: heartbeat must be finite")
        return 1
    age = time.time() - heartbeat
    if age < -max_age:
        print(f"invalid health-check state: heartbeat is {-age:.0f}s in the future")
        return 1
    if age > max_age:
        print(f"stale heartbeat: {age:.0f}s")
        return 1
    print(json.dumps(state, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
