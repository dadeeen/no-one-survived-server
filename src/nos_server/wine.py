from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Callable

from .settings import Settings


WINE = "/usr/bin/wine"
WINEBOOT = "/usr/bin/wineboot"
WINESERVER = "/usr/bin/wineserver"
XVFB_RUN = "/usr/bin/xvfb-run"
HEADLESS_WINE_DLL_OVERRIDES = "mscoree,mshtml,winemenubuilder.exe="


class WineError(RuntimeError):
    pass


def wine_environment(settings: Settings) -> dict[str, str]:
    env = os.environ.copy()
    library_paths = [str(settings.server_dir / "linux64")]
    library_paths.extend(
        component
        for component in env.get("LD_LIBRARY_PATH", "").split(":")
        if component
    )
    env.update(
        {
            "HOME": str(settings.home_dir),
            "USER": "nos",
            "LOGNAME": "nos",
            "WINEPREFIX": str(settings.wine_prefix),
            "WINEARCH": "win64",
            "WINEDEBUG": settings.wine_debug,
            "WINEDLLOVERRIDES": env.get(
                "WINEDLLOVERRIDES", HEADLESS_WINE_DLL_OVERRIDES
            ),
            "SteamAppId": "1963370",
            "XDG_RUNTIME_DIR": str(settings.runtime_dir / "xdg"),
            "LD_LIBRARY_PATH": ":".join(library_paths),
        }
    )
    return env


def _wine_version() -> str:
    result = subprocess.run(
        [WINE, "--version"], check=True, text=True, capture_output=True
    )
    return result.stdout.strip()


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
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired as exc:
        raise WineError("wineboot did not terminate after SIGKILL") from exc


def _stop_wineserver(env: dict[str, str]) -> None:
    try:
        subprocess.run([WINESERVER, "-k"], env=env, check=False, timeout=30)
        subprocess.run([WINESERVER, "-w"], env=env, check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WineError("wineserver did not stop after prefix initialization") from exc


def _xvfb_wineboot_command() -> list[str]:
    script = (
        f"{WINEBOOT} --init\n"
        "wineboot_status=$?\n"
        f"{WINESERVER} -k || true\n"
        f"{WINESERVER} -w || true\n"
        'exit "$wineboot_status"\n'
    )
    return [XVFB_RUN, "-a", "/bin/sh", "-c", script]


def prepare_wine_prefix(
    settings: Settings, heartbeat: Callable[[], None] | None = None
) -> str:
    settings.home_dir.mkdir(parents=True, exist_ok=True)
    xdg = settings.runtime_dir / "xdg"
    xdg.mkdir(parents=True, exist_ok=True, mode=0o700)
    current_version = _wine_version()
    previous_version = None
    try:
        previous_version = settings.wine_version_file.read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        pass
    prefix_initialized = (settings.wine_prefix / "system.reg").exists()
    reset = settings.reset_wineprefix or (
        settings.reset_wineprefix_on_version_change
        and prefix_initialized
        and previous_version != current_version
    )
    if reset and settings.wine_prefix.exists():
        print(
            f"[wine] Recreating prefix (previous={previous_version!r}, current={current_version!r})",
            flush=True,
        )
        shutil.rmtree(settings.wine_prefix)
    settings.wine_prefix.parent.mkdir(parents=True, exist_ok=True)
    env = wine_environment(settings)
    if not (settings.wine_prefix / "system.reg").exists():
        command = [WINEBOOT, "--init"]
        if settings.use_xvfb:
            command = _xvfb_wineboot_command()
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            start_new_session=True,
        )
        if process.stdout is None:
            process.kill()
            raise WineError("wineboot output pipe was not created")
        stdout = process.stdout

        def stream_output() -> None:
            for line in stdout:
                print(f"[wineboot] {line}", end="", flush=True)
                if heartbeat:
                    heartbeat()

        reader = threading.Thread(
            target=stream_output, name="wineboot-output", daemon=True
        )
        reader.start()
        deadline = time.monotonic() + settings.wineboot_timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print(
                    f"[wine] wineboot timed out after "
                    f"{settings.wineboot_timeout_seconds}s",
                    flush=True,
                )
                _terminate_process_group(process)
                reader.join(timeout=5)
                raise WineError(
                    "wineboot --init timed out after "
                    f"{settings.wineboot_timeout_seconds} seconds"
                )
            try:
                return_code = process.wait(timeout=min(5.0, remaining))
                break
            except subprocess.TimeoutExpired:
                if heartbeat:
                    heartbeat()
        reader.join(timeout=5)
        if return_code != 0:
            raise WineError(f"wineboot --init failed with exit code {return_code}")
        if not settings.use_xvfb:
            _stop_wineserver(env)
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    settings.wine_version_file.write_text(current_version + "\n", encoding="utf-8")
    return current_version
