from __future__ import annotations

import signal
import socket
import subprocess
import sys
import threading
import time
import traceback

from .a2s import A2SError, query_info
from .configuration import apply_configuration
from .control import ControlServer
from .server_process import ServerProcess
from .settings import Settings, SettingsError
from .state import StateStore
from .steamcmd import UpdateError, ensure_saved_link, update_due, update_server
from .wake import WakeListener
from .wine import WineError, prepare_wine_prefix


class Supervisor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.state = StateStore(settings.state_file)
        self.shutdown_event = threading.Event()
        self.wake_event = threading.Event()
        self.sleep_event = threading.Event()
        self.control = ControlServer(settings.control_socket, self.dispatch_control)
        self.server: ServerProcess | None = None
        self.prepared = False
        self.last_log_player_count = 0
        self.last_stop_monotonic = 0.0
        self.crash_restarts = 0

    def dispatch_control(self, command: str) -> dict[str, object]:
        if command == "status":
            return {"ok": True, **self.state.snapshot()}
        if command == "wake":
            current = self.state.snapshot().get("state")
            if current in {"STARTING", "RUNNING", "IDLE"}:
                return {
                    "ok": True,
                    "message": "server already active",
                    "state": current,
                }
            self.wake_event.set()
            return {"ok": True, "message": "wake requested"}
        if command == "sleep":
            current = self.state.snapshot().get("state")
            if current == "SLEEPING":
                return {
                    "ok": True,
                    "message": "server already sleeping",
                    "state": current,
                }
            self.sleep_event.set()
            return {"ok": True, "message": "sleep requested"}
        return {"ok": False, "error": f"unknown command: {command}"}

    def install_signal_handlers(self) -> None:
        def shutdown(signum: int, _frame: object) -> None:
            print(f"[supervisor] Received signal {signum}; shutting down", flush=True)
            self.shutdown_event.set()
            self.wake_event.set()
            self.sleep_event.set()

        def wake(_signum: int, _frame: object) -> None:
            print("[supervisor] SIGUSR1 wake requested", flush=True)
            self.wake_event.set()

        def sleep(_signum: int, _frame: object) -> None:
            print("[supervisor] SIGUSR2 sleep requested", flush=True)
            self.sleep_event.set()

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGUSR1, wake)
        signal.signal(signal.SIGUSR2, sleep)

    def ensure_directories(self) -> None:
        for path in (
            self.settings.data_dir,
            self.settings.server_dir,
            self.settings.saved_dir,
            self.settings.steamcmd_dir,
            self.settings.state_dir,
            self.settings.runtime_dir,
            self.settings.home_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def perform_update(self, required: bool = False) -> bool:
        self.state.set_state("UPDATING", last_error=None)
        try:
            update_server(self.settings, self.state.touch)
            print("[update] Server files are ready", flush=True)
            return True
        except UpdateError as exc:
            print(f"[update] ERROR: {exc}", flush=True)
            self.state.update(last_error=str(exc))
            if required or not self.settings.start_on_update_failure:
                raise
            print(
                "[update] Continuing with existing files because START_ON_UPDATE_FAILURE=true",
                flush=True,
            )
            return False

    def prepare(self, initial: bool = False, update: bool = False) -> None:
        del initial
        self.state.set_state("PREPARING", last_error=None)
        self.ensure_directories()
        needs_install = not self.settings.executable.exists()
        if update or needs_install:
            self.perform_update(required=needs_install)
        ensure_saved_link(self.settings)
        version = prepare_wine_prefix(self.settings, self.state.touch)
        applied = apply_configuration(self.settings)
        if applied:
            print("[config] Applied: " + ", ".join(applied), flush=True)
        else:
            print(
                "[config] No environment overrides; existing Game.ini retained",
                flush=True,
            )
        self.prepared = True
        self.state.update(
            wine_version=version, executable=str(self.settings.executable)
        )

    def prepare_initial(self, update: bool) -> bool:
        attempt = 0
        while not self.shutdown_event.is_set():
            try:
                self.prepare(initial=True, update=update)
                return True
            except (
                UpdateError,
                WineError,
                OSError,
                subprocess.SubprocessError,
            ) as exc:
                attempt += 1
                delay = self.settings.update_retry_delay_seconds
                print(
                    f"[supervisor] Initial preparation failed: {exc}; "
                    f"retrying in {delay}s (attempt {attempt})",
                    file=sys.stderr,
                    flush=True,
                )
                self.state.set_state(
                    "ERROR",
                    last_error=str(exc),
                    pid=None,
                    startup_retry_attempt=attempt,
                    retry_in_seconds=delay,
                )
                if self.shutdown_event.wait(delay):
                    return False
        return False

    def _log_activity(self, count: int) -> None:
        self.last_log_player_count = count
        self.state.update(log_players=count)

    def _cancel_start_if_sleep_requested(self) -> bool:
        if not self.sleep_event.is_set():
            return False
        self.sleep_event.clear()
        self.state.set_state(
            "SLEEPING",
            players=0,
            pid=None,
            ready=False,
            wake_source=None,
        )
        print("[supervisor] Start cancelled by sleep request", flush=True)
        return True

    def start_server(self, wake_source: str | None = None) -> bool:
        self.wake_event.clear()
        if not self.prepared:
            self.prepare(update=not self.settings.executable.exists())
        if self._cancel_start_if_sleep_requested():
            return False
        if self.settings.update_on_wake:
            try:
                self.perform_update(required=False)
            except UpdateError as exc:
                delay = self.settings.update_retry_delay_seconds
                print(
                    f"[update] Wake cancelled after update failure: {exc}; "
                    f"returning to sleep for at least {delay}s",
                    file=sys.stderr,
                    flush=True,
                )
                self.state.set_state(
                    "ERROR",
                    last_error=str(exc),
                    pid=None,
                    retry_in_seconds=delay,
                )
                self.shutdown_event.wait(delay)
                return False
            ensure_saved_link(self.settings)
            apply_configuration(self.settings)
        if self._cancel_start_if_sleep_requested():
            return False
        self.last_log_player_count = 0
        self.state.set_state(
            "STARTING",
            players=None,
            log_players=0,
            ready=False,
            wake_source=wake_source,
            last_error=None,
        )
        self.server = ServerProcess(self.settings, self._log_activity)
        pid = self.server.start()
        self.state.update(pid=pid)
        print(f"[supervisor] Server started with PID {pid}", flush=True)
        return True

    def stop_server(self, reason: str) -> None:
        if not self.server:
            return
        self.state.set_state("STOPPING", stop_reason=reason)
        print(f"[supervisor] Stopping server: {reason}", flush=True)
        return_code = self.server.stop()
        print(f"[supervisor] Server stopped with exit code {return_code}", flush=True)
        self.server = None
        self.last_stop_monotonic = time.monotonic()
        self.state.update(pid=None, players=0, ready=False, last_exit_code=return_code)

    def monitor_server(self) -> str:
        if self.server is None:
            raise RuntimeError("monitor_server called without a server process")
        started = time.monotonic()
        next_query = started
        idle_since: float | None = None
        successful_zero_queries = 0
        a2s_ever_succeeded = False
        ready_deadline = started + self.settings.server_ready_timeout_seconds

        while not self.shutdown_event.is_set():
            self.state.touch()
            if self.sleep_event.is_set():
                self.stop_server("manual sleep request")
                return "sleep"
            return_code = self.server.poll()
            if return_code is not None:
                self.state.update(pid=None, ready=False, last_exit_code=return_code)
                self.server = None
                return "crash"

            now = time.monotonic()
            if (
                self.crash_restarts
                and self.settings.crash_restart_reset_seconds > 0
                and now - started >= self.settings.crash_restart_reset_seconds
            ):
                self.crash_restarts = 0
                self.state.update(crash_restarts=0)
            if self.server.ready.is_set():
                if idle_since is None:
                    self.state.set_state("RUNNING", ready=True, readiness_timeout=False)
                else:
                    self.state.update(ready=True, readiness_timeout=False)
            elif now >= ready_deadline:
                if idle_since is None:
                    self.state.set_state("RUNNING", ready=False, readiness_timeout=True)
                else:
                    self.state.update(ready=False, readiness_timeout=True)

            if now >= next_query:
                next_query = now + self.settings.idle_check_interval_seconds
                try:
                    info = query_info(
                        self.settings.a2s_query_host,
                        self.settings.query_port,
                        self.settings.a2s_timeout_seconds,
                    )
                    a2s_ever_succeeded = True
                    players = info.players
                    self.state.update(
                        players=players,
                        max_players=info.max_players,
                        server_name=info.name,
                        map=info.map_name,
                        a2s_ok=True,
                        a2s_error=None,
                    )
                    if players > 0:
                        idle_since = None
                        successful_zero_queries = 0
                        self.state.set_state("RUNNING", players=players, ready=True)
                    else:
                        successful_zero_queries += 1
                        if idle_since is None:
                            idle_since = now
                        self.state.set_state(
                            "IDLE", players=0, ready=self.server.ready.is_set()
                        )
                except (A2SError, OSError, socket.timeout) as exc:
                    self.state.update(a2s_ok=False, a2s_error=str(exc))
                    successful_zero_queries = 0
                    if self.settings.allow_log_only_idle and not a2s_ever_succeeded:
                        if self.last_log_player_count == 0 and idle_since is None:
                            idle_since = now
                        elif self.last_log_player_count > 0:
                            idle_since = None
                    else:
                        idle_since = None

                uptime = now - started
                if (
                    self.settings.auto_sleep_enabled
                    and idle_since is not None
                    and uptime >= self.settings.min_uptime_seconds
                    and now - idle_since >= self.settings.idle_timeout_seconds
                    and (
                        successful_zero_queries
                        >= self.settings.idle_min_successful_queries
                        or (
                            self.settings.allow_log_only_idle and not a2s_ever_succeeded
                        )
                    )
                ):
                    self.stop_server("idle timeout")
                    return "sleep"
            time.sleep(1)

        self.stop_server("container shutdown")
        return "shutdown"

    def wait_for_wake(self) -> str:
        if self.settings.wake_arm_delay_seconds > 0 and self.last_stop_monotonic:
            deadline = self.last_stop_monotonic + self.settings.wake_arm_delay_seconds
            while not self.shutdown_event.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.state.set_state(
                    "SLEEPING", wake_armed=False, arm_in_seconds=round(remaining, 1)
                )
                if self.wake_event.wait(min(0.25, remaining)):
                    if self.shutdown_event.is_set():
                        return "shutdown"
                    self.wake_event.clear()
                    print("[wake] Manual wake requested during arm delay", flush=True)
                    return "manual"
        if self.shutdown_event.is_set():
            return "shutdown"
        self.sleep_event.clear()
        if self.wake_event.is_set():
            self.wake_event.clear()
            print("[wake] Manual wake requested", flush=True)
            return "manual"

        ports: list[int] = []
        if self.settings.wake_on_game_port:
            ports.append(self.settings.game_port)
        if self.settings.wake_on_query_port:
            ports.append(self.settings.query_port)
        self.state.set_state(
            "SLEEPING",
            wake_armed=bool(ports),
            arm_in_seconds=0,
            wake_ports=ports,
            players=0,
            pid=None,
        )
        print(
            f"[wake] Sleeping; listening on UDP ports {ports or 'none (manual wake only)'}",
            flush=True,
        )
        extra_networks = ",".join(self.settings.wake_allowed_networks) or "none"
        print(
            f"[wake] Source policy={self.settings.wake_source_policy}; "
            f"additional networks={extra_networks}",
            flush=True,
        )
        listener = WakeListener(
            self.settings.wake_bind_address,
            ports,
            self.settings.wake_source_policy,
            self.settings.wake_allowed_networks,
            self.settings.wake_packet_count,
            self.settings.wake_packet_window_seconds,
            self.settings.wake_ignore_empty_packets,
        )

        try:
            while not self.shutdown_event.is_set():
                self.state.touch()
                if update_due(self.settings):
                    try:
                        self.perform_update(required=False)
                    except UpdateError as exc:
                        print(
                            f"[update] Periodic update failed: {exc}; remaining asleep",
                            file=sys.stderr,
                            flush=True,
                        )
                    else:
                        ensure_saved_link(self.settings)
                        apply_configuration(self.settings)
                    self.state.set_state(
                        "SLEEPING",
                        wake_armed=bool(ports),
                        wake_ports=ports,
                    )
                event = listener.wait(self.wake_event, timeout=5.0)
                if self.shutdown_event.is_set():
                    return "shutdown"
                if self.wake_event.is_set():
                    self.wake_event.clear()
                    print("[wake] Manual wake requested", flush=True)
                    return "manual"
                if event:
                    source = f"{event.source_ip}:{event.source_port} -> UDP/{event.local_port}"
                    print(
                        f"[wake] Accepted wake packet from {source} "
                        f"({event.packet_size} bytes)",
                        flush=True,
                    )
                    self.state.update(wake_source=source)
                    return source
            return "shutdown"
        finally:
            listener.close()

    def run(self) -> int:
        self.install_signal_handlers()
        try:
            self.control.start()
            update = (
                self.settings.update_on_container_start
                or not self.settings.executable.exists()
            )
            if self.settings.prepare_on_container_start or update:
                if not self.prepare_initial(update):
                    self.state.set_state("STOPPED", pid=None, players=0, ready=False)
                    return 0
            start_now = self.settings.start_server_on_container_start
            wake_source: str | None = "container start" if start_now else None

            while not self.shutdown_event.is_set():
                if not start_now:
                    wake_source = self.wait_for_wake()
                    if wake_source == "shutdown":
                        break
                if not self.start_server(wake_source):
                    start_now = False
                    continue
                result = self.monitor_server()
                if result == "shutdown":
                    break
                if result == "crash":
                    self.crash_restarts += 1
                    message = (
                        "server exited unexpectedly "
                        f"(restart {self.crash_restarts}/"
                        f"{self.settings.max_crash_restarts})"
                    )
                    print(f"[supervisor] {message}", flush=True)
                    if (
                        not self.settings.restart_on_crash
                        or self.crash_restarts > self.settings.max_crash_restarts
                    ):
                        self.state.set_state("ERROR", last_error=message)
                        return 1
                    self.shutdown_event.wait(self.settings.crash_restart_delay_seconds)
                    start_now = True
                    wake_source = "crash restart"
                    continue
                self.crash_restarts = 0
                start_now = False
            self.state.set_state("STOPPED", pid=None, players=0, ready=False)
            return 0
        except (
            SettingsError,
            UpdateError,
            WineError,
            OSError,
            subprocess.SubprocessError,
        ) as exc:
            print(f"[supervisor] FATAL: {exc}", file=sys.stderr, flush=True)
            traceback.print_exc()
            self.state.set_state("ERROR", last_error=str(exc), pid=None)
            return 1
        except Exception as exc:
            print(f"[supervisor] UNEXPECTED FATAL: {exc}", file=sys.stderr, flush=True)
            traceback.print_exc()
            self.state.set_state("ERROR", last_error=f"unexpected: {exc}", pid=None)
            return 1
        finally:
            if self.server:
                self.stop_server("supervisor exit")
            self.control.stop()


def main() -> int:
    try:
        settings = Settings.from_env()
    except SettingsError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    return Supervisor(settings).run()


if __name__ == "__main__":
    sys.exit(main())
