from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .settings import Settings


APP_ID = "2329680"
MISSING_CONFIGURATION_MARKER = (
    f"Failed to install app '{APP_ID}' (Missing configuration)"
)
MISSING_CONFIGURATION_RETRY_DELAY_SECONDS = 30


class UpdateError(RuntimeError):
    pass


def _copy_contents(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir() and not item.is_symlink():
            shutil.copytree(item, target, dirs_exist_ok=True)
        elif item.is_symlink():
            if target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(os.readlink(item))
        else:
            shutil.copy2(item, target)


def ensure_saved_link(settings: Settings) -> None:
    target = settings.server_saved_path
    settings.saved_dir.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() and target.resolve() == settings.saved_dir.resolve():
        return
    if target.exists() or target.is_symlink():
        if target.is_dir() and not target.is_symlink():
            if not any(settings.saved_dir.iterdir()):
                _copy_contents(target, settings.saved_dir)
                shutil.rmtree(target)
            else:
                orphan = (
                    settings.state_dir / f"orphaned-server-saved-{int(time.time())}"
                )
                orphan.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(orphan))
        else:
            target.unlink()
    target.symlink_to(settings.saved_dir, target_is_directory=True)


def _write_timestamp(path: Path, timestamp: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = time.time() if timestamp is None else timestamp
    path.write_text(f"{value:.6f}\n", encoding="ascii")


def _read_timestamp(path: Path) -> float | None:
    try:
        return float(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=10)


def _steamcmd_command(settings: Settings, *, refresh_metadata: bool) -> list[str]:
    steamcmd = settings.steamcmd_dir / "steamcmd.sh"
    command = [
        str(steamcmd),
        "+@sSteamCmdForcePlatformType",
        "windows",
        "+force_install_dir",
        str(settings.server_dir),
        "+login",
        "anonymous",
    ]
    if refresh_metadata:
        command.extend(["+app_info_update", "1"])
    command.extend(["+app_update", APP_ID])
    if settings.validate_on_update:
        command.append("validate")
    command.append("+quit")
    return command


def _run_steamcmd(
    settings: Settings,
    heartbeat: Callable[[], None] | None,
    *,
    refresh_metadata: bool,
) -> tuple[int, bool]:
    command = _steamcmd_command(settings, refresh_metadata=refresh_metadata)
    if refresh_metadata:
        print(
            f"[update] Refreshing Steam metadata and retrying app {APP_ID}",
            flush=True,
        )
    else:
        print(f"[update] Running SteamCMD for app {APP_ID}", flush=True)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=os.environ.copy(),
        start_new_session=True,
    )
    if process.stdout is None:
        process.kill()
        raise UpdateError("SteamCMD output pipe was not created")
    stdout = process.stdout
    missing_configuration = threading.Event()

    def stream_output() -> None:
        for line in stdout:
            print(f"[steamcmd] {line}", end="", flush=True)
            if MISSING_CONFIGURATION_MARKER in line:
                missing_configuration.set()
            if heartbeat:
                heartbeat()

    reader = threading.Thread(target=stream_output, name="steamcmd-output", daemon=True)
    reader.start()
    try:
        return_code = process.wait(timeout=settings.steamcmd_timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        print(
            f"[update] SteamCMD timed out after {settings.steamcmd_timeout_seconds}s",
            flush=True,
        )
        _terminate_process_group(process)
        reader.join(timeout=5)
        raise UpdateError(
            f"SteamCMD timed out after {settings.steamcmd_timeout_seconds} seconds"
        ) from exc
    reader.join(timeout=5)
    return return_code, missing_configuration.is_set()


def _update_server(
    settings: Settings, heartbeat: Callable[[], None] | None = None
) -> None:
    steamcmd = settings.steamcmd_dir / "steamcmd.sh"
    if not steamcmd.exists():
        raise UpdateError(f"SteamCMD not found at {steamcmd}")
    settings.server_dir.mkdir(parents=True, exist_ok=True)
    _write_timestamp(settings.update_attempt_stamp)
    return_code, missing_configuration = _run_steamcmd(
        settings,
        heartbeat,
        refresh_metadata=False,
    )
    ensure_saved_link(settings)
    if missing_configuration and not settings.executable.exists():
        print(
            "[update] Steam app configuration is not available yet; "
            f"retrying once in {MISSING_CONFIGURATION_RETRY_DELAY_SECONDS}s",
            flush=True,
        )
        time.sleep(MISSING_CONFIGURATION_RETRY_DELAY_SECONDS)
        return_code, _ = _run_steamcmd(
            settings,
            heartbeat,
            refresh_metadata=True,
        )
        ensure_saved_link(settings)
    if return_code != 0 or not settings.executable.exists():
        raise UpdateError(
            f"SteamCMD failed (exit {return_code}); expected executable missing: {settings.executable}"
        )
    _write_timestamp(settings.update_stamp)


def update_server(
    settings: Settings, heartbeat: Callable[[], None] | None = None
) -> None:
    try:
        _update_server(settings, heartbeat)
    except UpdateError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpdateError(f"SteamCMD operation failed: {exc}") from exc


def update_due(settings: Settings, now: float | None = None) -> bool:
    if settings.update_interval_seconds <= 0:
        return False
    current = time.time() if now is None else now
    last_success = _read_timestamp(settings.update_stamp)
    last_attempt = _read_timestamp(settings.update_attempt_stamp)

    if (
        last_success is not None
        and current - last_success < settings.update_interval_seconds
    ):
        return False
    if (
        last_attempt is not None
        and (last_success is None or last_attempt > last_success)
        and current - last_attempt < settings.update_retry_delay_seconds
    ):
        return False
    return True
