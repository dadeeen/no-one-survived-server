from __future__ import annotations

import os
import re
import shlex
import signal
import subprocess
import threading
from collections.abc import Callable

from .settings import Settings
from .wine import WINE, WINESERVER, XVFB_RUN, wine_environment


READY_RE = re.compile(
    r"LogSteamSocketsAPI: Verbose: SteamSockets API: Log AuthStatus .*:\s+OK\s+\(OK\)"
)
JOIN_RE = re.compile(
    r"LogNet: Login request: \?Name=(?P<name>.+?) userId:.*\[(?P<id>.+?)]"
)
LEAVE_RE = re.compile(
    r"UChannel::Close: Sending CloseBunch\..*UniqueId:.*\[(?P<id>.+?)]"
)


class ServerProcess:
    def __init__(
        self, settings: Settings, on_log_activity: Callable[[int], None] | None = None
    ) -> None:
        self.settings = settings
        self.on_log_activity = on_log_activity
        self.process: subprocess.Popen[str] | None = None
        self.ready = threading.Event()
        self.log_players: set[str] = set()
        self._reader: threading.Thread | None = None

    def command(self) -> list[str]:
        command = [
            WINE,
            str(self.settings.executable),
            "WRSH",
            "-server",
            "-stdout",
            "-FullStdOutLogOutput",
            f"-Port={self.settings.game_port}",
            f"-QueryPort={self.settings.query_port}",
            f"-MultiHome={self.settings.bind_address}",
        ]
        if self.settings.extra_server_args:
            command.extend(shlex.split(self.settings.extra_server_args))
        if self.settings.use_xvfb:
            command = [XVFB_RUN, "-a", *command]
        return command

    def start(self) -> int:
        if not self.settings.executable.exists():
            raise FileNotFoundError(self.settings.executable)
        self.ready.clear()
        self.log_players.clear()
        env = wine_environment(self.settings)
        self.process = subprocess.Popen(
            self.command(),
            cwd=self.settings.server_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            start_new_session=True,
        )
        self._reader = threading.Thread(
            target=self._read_output, name="server-output", daemon=True
        )
        self._reader.start()
        return self.process.pid

    def _read_output(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            print(f"[server] {line}", end="", flush=True)
            if READY_RE.search(line):
                self.ready.set()
            match = JOIN_RE.search(line)
            if match:
                self.log_players.add(match.group("id"))
                if self.on_log_activity:
                    self.on_log_activity(len(self.log_players))
                continue
            match = LEAVE_RE.search(line)
            if match:
                self.log_players.discard(match.group("id"))
                if self.on_log_activity:
                    self.on_log_activity(len(self.log_players))

    def poll(self) -> int | None:
        return None if self.process is None else self.process.poll()

    def stop(self) -> int | None:
        if self.process is None:
            return None
        process = self.process
        if process.poll() is not None:
            return process.returncode
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            return process.wait(timeout=self.settings.server_stop_timeout_seconds)
        except subprocess.TimeoutExpired:
            print("[server] Graceful stop timed out; sending SIGTERM", flush=True)
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            return process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            print("[server] SIGTERM timed out; terminating Wine server", flush=True)
        try:
            subprocess.run(
                [WINESERVER, "-k"],
                env=wine_environment(self.settings),
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"[server] wineserver shutdown failed: {exc}", flush=True)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            return process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            print(
                "[server] Process did not exit after SIGKILL; leaving cleanup to tini",
                flush=True,
            )
            return process.poll()
