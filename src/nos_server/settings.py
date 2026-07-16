from __future__ import annotations

import ipaddress
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TRUE_VALUES = {"1", "true", "yes", "on", "y"}
FALSE_VALUES = {"0", "false", "no", "off", "n"}


class SettingsError(ValueError):
    """Raised for invalid container configuration."""


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise SettingsError(f"{name} must be a boolean, got {raw!r}")


def env_int(
    name: str, default: int, minimum: int | None = None, maximum: int | None = None
) -> int:
    raw = os.getenv(name)
    try:
        value = default if raw is None or raw == "" else int(raw)
    except ValueError as exc:
        raise SettingsError(f"{name} must be an integer, got {raw!r}") from exc
    if minimum is not None and value < minimum:
        raise SettingsError(f"{name} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise SettingsError(f"{name} must be <= {maximum}, got {value}")
    return value


def env_float(name: str, default: float, minimum: float | None = None) -> float:
    raw = os.getenv(name)
    try:
        value = default if raw is None or raw == "" else float(raw)
    except ValueError as exc:
        raise SettingsError(f"{name} must be a number, got {raw!r}") from exc
    if not math.isfinite(value):
        raise SettingsError(f"{name} must be a finite number, got {raw!r}")
    if minimum is not None and value < minimum:
        raise SettingsError(f"{name} must be >= {minimum}, got {value}")
    return value


def read_secret(name: str) -> str | None:
    file_name = os.getenv(f"{name}_FILE")
    direct = os.getenv(name)
    if file_name and direct not in (None, ""):
        raise SettingsError(f"Set only one of {name} and {name}_FILE")
    if file_name:
        path = Path(file_name)
        try:
            value = path.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as exc:
            raise SettingsError(f"Cannot read {name}_FILE at {path}: {exc}") from exc
        if not value.strip():
            raise SettingsError(f"{name}_FILE at {path} must not be empty")
        return value
    if direct is None or direct == "":
        return None
    return direct


def read_json_object(name: str) -> dict[str, Any]:
    raw = read_secret(name)
    if raw is None or raw.strip() == "":
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SettingsError(f"{name} must contain valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SettingsError(f"{name} must be a JSON object")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path
    server_dir: Path
    saved_dir: Path
    wine_prefix: Path
    steamcmd_dir: Path
    state_dir: Path
    runtime_dir: Path
    home_dir: Path

    game_port: int
    query_port: int
    bind_address: str

    prepare_on_container_start: bool
    start_server_on_container_start: bool
    update_on_container_start: bool
    update_on_wake: bool
    update_interval_seconds: int
    update_retry_delay_seconds: int
    steamcmd_timeout_seconds: int
    validate_on_update: bool
    start_on_update_failure: bool

    auto_sleep_enabled: bool
    idle_timeout_seconds: int
    idle_check_interval_seconds: int
    min_uptime_seconds: int
    idle_min_successful_queries: int
    a2s_timeout_seconds: float
    a2s_query_host: str
    allow_log_only_idle: bool

    wake_on_game_port: bool
    wake_on_query_port: bool
    wake_bind_address: str
    wake_source_policy: str
    wake_allowed_networks: tuple[str, ...]
    wake_packet_count: int
    wake_packet_window_seconds: int
    wake_arm_delay_seconds: int
    wake_ignore_empty_packets: bool

    server_ready_timeout_seconds: int
    server_stop_timeout_seconds: int
    restart_on_crash: bool
    crash_restart_delay_seconds: int
    max_crash_restarts: int
    crash_restart_reset_seconds: int
    extra_server_args: str

    reset_wineprefix: bool
    reset_wineprefix_on_version_change: bool
    wineboot_timeout_seconds: int
    wine_debug: str
    use_xvfb: bool

    state_file: Path
    control_socket: Path
    game_ini: Path
    engine_ini: Path
    template_game_ini: Path
    template_engine_ini: Path

    @classmethod
    def from_env(cls) -> "Settings":
        data = Path(os.getenv("DATA_DIR", "/data"))
        runtime = Path(os.getenv("RUNTIME_DIR", "/run/nos"))
        if not data.is_absolute():
            raise SettingsError("DATA_DIR must be an absolute path")
        if not runtime.is_absolute():
            raise SettingsError("RUNTIME_DIR must be an absolute path")
        server = Path(os.getenv("SERVER_DIR", str(data / "server")))
        saved = Path(os.getenv("SAVED_DIR", str(data / "saved")))
        state = Path(os.getenv("STATE_DIR", str(data / "state")))
        game_port = env_int("GAME_PORT", 7777, 1, 65535)
        query_port = env_int("QUERY_PORT", 27015, 1, 65535)
        if game_port == query_port:
            raise SettingsError("GAME_PORT and QUERY_PORT must be different")
        wake_source_policy = os.getenv("WAKE_SOURCE_POLICY", "private").strip().lower()
        if wake_source_policy not in {"private", "allowlist", "any"}:
            raise SettingsError(
                "WAKE_SOURCE_POLICY must be one of: private, allowlist, any"
            )
        allowed = tuple(
            item.strip()
            for item in os.getenv("WAKE_ALLOWED_NETWORKS", "").split(",")
            if item.strip()
        )
        try:
            for network in allowed:
                parsed = ipaddress.ip_network(network, strict=False)
                if parsed.version != 4:
                    raise SettingsError(
                        "WAKE_ALLOWED_NETWORKS currently supports IPv4 CIDRs only"
                    )
        except ValueError as exc:
            raise SettingsError(f"Invalid WAKE_ALLOWED_NETWORKS entry: {exc}") from exc
        if wake_source_policy == "allowlist" and not allowed:
            raise SettingsError(
                "WAKE_ALLOWED_NETWORKS must not be empty when "
                "WAKE_SOURCE_POLICY=allowlist"
            )
        bind_address = os.getenv("MULTIHOME", "0.0.0.0")
        wake_bind_address = os.getenv("WAKE_BIND_ADDRESS", "0.0.0.0")
        try:
            ipaddress.IPv4Address(bind_address)
            ipaddress.IPv4Address(wake_bind_address)
        except ipaddress.AddressValueError as exc:
            raise SettingsError(
                f"MULTIHOME and WAKE_BIND_ADDRESS must be IPv4 addresses: {exc}"
            ) from exc
        automatic_a2s_host = "127.0.0.1" if bind_address == "0.0.0.0" else bind_address
        configured_a2s_host = os.getenv("A2S_QUERY_HOST", "").strip()
        a2s_query_host = configured_a2s_host or automatic_a2s_host
        try:
            ipaddress.IPv4Address(a2s_query_host)
        except ipaddress.AddressValueError as exc:
            raise SettingsError(
                f"A2S_QUERY_HOST must be an IPv4 address: {exc}"
            ) from exc
        state_file_value = os.getenv("STATE_FILE", "").strip()
        control_socket_value = os.getenv("CONTROL_SOCKET", "").strip()
        settings = cls(
            data_dir=data,
            server_dir=server,
            saved_dir=saved,
            wine_prefix=Path(os.getenv("WINEPREFIX", str(data / "wine"))),
            steamcmd_dir=Path(os.getenv("STEAMCMD_DIR", str(data / "steamcmd"))),
            state_dir=state,
            runtime_dir=runtime,
            home_dir=Path(os.getenv("HOME", str(data / "home"))),
            game_port=game_port,
            query_port=query_port,
            bind_address=bind_address,
            prepare_on_container_start=env_bool("PREPARE_ON_CONTAINER_START", True),
            start_server_on_container_start=env_bool(
                "START_SERVER_ON_CONTAINER_START", True
            ),
            update_on_container_start=env_bool("UPDATE_ON_CONTAINER_START", True),
            update_on_wake=env_bool("UPDATE_ON_WAKE", False),
            update_interval_seconds=env_int("UPDATE_INTERVAL_SECONDS", 0, 0),
            update_retry_delay_seconds=env_int("UPDATE_RETRY_DELAY_SECONDS", 900, 5),
            steamcmd_timeout_seconds=env_int("STEAMCMD_TIMEOUT_SECONDS", 3600, 60),
            validate_on_update=env_bool("VALIDATE_ON_UPDATE", False),
            start_on_update_failure=env_bool("START_ON_UPDATE_FAILURE", False),
            auto_sleep_enabled=env_bool("AUTO_SLEEP_ENABLED", True),
            idle_timeout_seconds=env_int("IDLE_TIMEOUT_SECONDS", 3600, 60),
            idle_check_interval_seconds=env_int("IDLE_CHECK_INTERVAL_SECONDS", 30, 5),
            min_uptime_seconds=env_int("MIN_UPTIME_SECONDS", 900, 0),
            idle_min_successful_queries=env_int("IDLE_MIN_SUCCESSFUL_QUERIES", 3, 1),
            a2s_timeout_seconds=env_float("A2S_TIMEOUT_SECONDS", 2.0, 0.1),
            a2s_query_host=a2s_query_host,
            allow_log_only_idle=env_bool("ALLOW_LOG_ONLY_IDLE", False),
            wake_on_game_port=env_bool("WAKE_ON_GAME_PORT", True),
            wake_on_query_port=env_bool("WAKE_ON_QUERY_PORT", True),
            wake_bind_address=wake_bind_address,
            wake_source_policy=wake_source_policy,
            wake_allowed_networks=allowed,
            wake_packet_count=env_int("WAKE_PACKET_COUNT", 1, 1, 20),
            wake_packet_window_seconds=env_int("WAKE_PACKET_WINDOW_SECONDS", 5, 1, 60),
            wake_arm_delay_seconds=env_int("WAKE_ARM_DELAY_SECONDS", 5, 0, 300),
            wake_ignore_empty_packets=env_bool("WAKE_IGNORE_EMPTY_PACKETS", True),
            server_ready_timeout_seconds=env_int(
                "SERVER_READY_TIMEOUT_SECONDS", 300, 30
            ),
            server_stop_timeout_seconds=env_int("SERVER_STOP_TIMEOUT_SECONDS", 90, 10),
            restart_on_crash=env_bool("RESTART_ON_CRASH", True),
            crash_restart_delay_seconds=env_int("CRASH_RESTART_DELAY_SECONDS", 15, 1),
            max_crash_restarts=env_int("MAX_CRASH_RESTARTS", 3, 0, 100),
            crash_restart_reset_seconds=env_int("CRASH_RESTART_RESET_SECONDS", 600, 0),
            extra_server_args=os.getenv("EXTRA_SERVER_ARGS", ""),
            reset_wineprefix=env_bool("RESET_WINEPREFIX", False),
            reset_wineprefix_on_version_change=env_bool(
                "RESET_WINEPREFIX_ON_VERSION_CHANGE", True
            ),
            wineboot_timeout_seconds=env_int("WINEBOOT_TIMEOUT_SECONDS", 600, 30),
            wine_debug=os.getenv("WINEDEBUG", "-all"),
            use_xvfb=env_bool("USE_XVFB", True),
            state_file=Path(state_file_value)
            if state_file_value
            else runtime / "state.json",
            control_socket=(
                Path(control_socket_value)
                if control_socket_value
                else runtime / "control.sock"
            ),
            game_ini=saved / "Config" / "WindowsServer" / "Game.ini",
            engine_ini=saved / "Config" / "WindowsServer" / "Engine.ini",
            template_game_ini=Path(
                os.getenv("GAME_INI_TEMPLATE", "/opt/nos/config/Game.ini.example")
            ),
            template_engine_ini=Path(
                os.getenv("ENGINE_INI_TEMPLATE", "/opt/nos/config/Engine.ini.example")
            ),
        )
        data_root = settings.data_dir.resolve(strict=False)
        if data_root == Path("/"):
            raise SettingsError("DATA_DIR must be an absolute path other than /")
        persistent_paths = {
            "SERVER_DIR": settings.server_dir,
            "SAVED_DIR": settings.saved_dir,
            "WINEPREFIX": settings.wine_prefix,
            "STEAMCMD_DIR": settings.steamcmd_dir,
            "STATE_DIR": settings.state_dir,
            "HOME": settings.home_dir,
        }
        for name, path in persistent_paths.items():
            if not path.is_absolute():
                raise SettingsError(f"{name} must be an absolute path")
            resolved = path.resolve(strict=False)
            if not resolved.is_relative_to(data_root):
                raise SettingsError(
                    f"{name} must be located below DATA_DIR ({data_root})"
                )
        runtime_root = settings.runtime_dir.resolve(strict=False)
        if runtime_root == Path("/"):
            raise SettingsError("RUNTIME_DIR must be an absolute path other than /")
        runtime_paths = {
            "STATE_FILE": settings.state_file,
            "CONTROL_SOCKET": settings.control_socket,
        }
        for name, path in runtime_paths.items():
            if not path.is_absolute() or path == Path("/"):
                raise SettingsError(f"{name} must be an absolute path other than /")
        return settings

    @property
    def executable(self) -> Path:
        return self.server_dir / "WRSH" / "Binaries" / "Win64" / "WRSHServer.exe"

    @property
    def server_saved_path(self) -> Path:
        return self.server_dir / "WRSH" / "Saved"

    @property
    def update_stamp(self) -> Path:
        return self.state_dir / "last-update"

    @property
    def update_attempt_stamp(self) -> Path:
        return self.state_dir / "last-update-attempt"

    @property
    def wine_version_file(self) -> Path:
        return self.state_dir / "wine-version"
