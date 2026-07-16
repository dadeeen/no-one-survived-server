from __future__ import annotations

import math
import os
import secrets
from typing import Callable

from .ini_merge import merge_ini
from .settings import Settings, SettingsError, read_json_object, read_secret


def _bool_text(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on", "y"}:
        return "True"
    if value in {"0", "false", "no", "off", "n"}:
        return "False"
    raise SettingsError(f"Expected a boolean value, got {raw!r}")


def _identity(raw: str) -> str:
    if any(character in raw for character in ("\r", "\n", "\x00")):
        raise SettingsError("INI values must not contain line breaks or NUL bytes")
    return raw


def _int_range(minimum: int, maximum: int) -> Callable[[str], str]:
    def convert(raw: str) -> str:
        try:
            value = int(raw)
        except ValueError as exc:
            raise SettingsError(
                f"Expected integer {minimum}..{maximum}, got {raw!r}"
            ) from exc
        if not minimum <= value <= maximum:
            raise SettingsError(f"Expected integer {minimum}..{maximum}, got {value}")
        return str(value)

    return convert


def _float_range(minimum: float, maximum: float) -> Callable[[str], str]:
    def convert(raw: str) -> str:
        try:
            value = float(raw)
        except ValueError as exc:
            raise SettingsError(
                f"Expected number {minimum}..{maximum}, got {raw!r}"
            ) from exc
        if not minimum <= value <= maximum:
            raise SettingsError(f"Expected number {minimum}..{maximum}, got {value}")
        return str(value)

    return convert


# env name -> (section, key, converter, secret)
MAPPINGS: dict[str, tuple[str, str, Callable[[str], str], bool]] = {
    "SERVER_NAME": ("ServerSetting", "ServerName", _identity, False),
    "SAVE_NAME": ("ServerSetting", "SaveName", _identity, False),
    "REQUIRE_PASSWORD": ("ServerSetting", "NeedPassword", _bool_text, False),
    "SERVER_PASSWORD": ("ServerSetting", "Password", _identity, True),
    "ADMIN_PASSWORD": ("ServerSetting", "AdminPassword", _identity, True),
    "MAP": ("ServerSetting", "OpenMap", _identity, False),
    "MAX_PLAYERS": ("ServerSetting", "MaxPlayers", _int_range(2, 50), False),
    "REGION": ("ServerSetting", "Region", _identity, False),
    "ZOMBIES_PER_PLAYER": (
        "ServerSetting",
        "NumOfZombieSpawn",
        _int_range(25, 100),
        False,
    ),
    "PVP": ("GameSettings", "PVP", _bool_text, False),
    "ZOMBIE_ATTACK": ("GameSettings", "ZombieAttack", _bool_text, False),
    "ZOMBIE_ATTACK_DAY": ("GameSettings", "ZombieAttackDay", _int_range(1, 30), False),
    "ATTACK_ZOMBIE_NUM": ("GameSettings", "AttackZombieNum", _int_range(1, 5), False),
    "ZOMBIE_NUM": ("GameSettings", "ZombieNum", _int_range(1, 3), False),
    "RUN_ZOMBIE_PERCENT": (
        "GameSettings",
        "RunZombiePercent",
        _float_range(0, 1),
        False,
    ),
    "ZOMBIE_STRENGTH": ("GameSettings", "ZombieStreng", _int_range(0, 3), False),
    "SPECIAL_ZOMBIE": ("GameSettings", "SpecialZombie", _bool_text, False),
    "YEAR_DAYS": ("GameSettings", "YearDay", _int_range(1, 365), False),
    "DAY_LENGTH": ("GameSettings", "DayLength", _int_range(1, 240), False),
    "PERMADEATH": ("GameSettings", "PermanentDead", _bool_text, False),
    "MATERIAL_AMOUNT": ("GameSettings", "MaterialNum", _float_range(0.1, 10), False),
    "ITEM_SPAWN": ("GameSettings", "ItemSpawn", _float_range(0.1, 10), False),
    "VIRUS_FATALITY_RATE": (
        "GameSettings",
        "VirusFatalityRate",
        _float_range(0, 1),
        False,
    ),
    "NOVICE_GIFT_BAG": ("GameSettings", "GiftBagForNovices", _bool_text, False),
    "NPC_ITEM_SPAWN": ("GameSettings", "NPCItemSpawn", _float_range(0.1, 10), False),
}


def build_updates() -> tuple[dict[str, dict[str, str]], list[str]]:
    updates: dict[str, dict[str, str]] = {}
    applied: list[str] = []
    for env_name, (section, key, convert, secret) in MAPPINGS.items():
        raw = read_secret(env_name) if secret else os.getenv(env_name)
        if raw is None or (not secret and raw == ""):
            continue
        if secret and not raw.strip():
            raise SettingsError(f"{env_name} must not be blank")
        value = convert(raw)
        updates.setdefault(section, {})[key] = value
        applied.append(f"{section}.{key}" + (" (secret)" if secret else ""))

    extra = read_json_object("GAME_INI_OVERRIDES")
    for section, values in extra.items():
        if not isinstance(section, str) or not isinstance(values, dict):
            raise SettingsError("GAME_INI_OVERRIDES must map section names to objects")
        if not section or any(
            character in section for character in ("\r", "\n", "\x00", "[", "]")
        ):
            raise SettingsError(
                f"Invalid INI section name in GAME_INI_OVERRIDES: {section!r}"
            )
        for key, value in values.items():
            if not isinstance(key, str) or isinstance(value, (dict, list)):
                raise SettingsError("GAME_INI_OVERRIDES values must be scalar")
            if not key or any(
                character in key for character in ("\r", "\n", "\x00", "=")
            ):
                raise SettingsError(f"Invalid INI key in GAME_INI_OVERRIDES: {key!r}")
            if isinstance(value, float) and not math.isfinite(value):
                raise SettingsError("GAME_INI_OVERRIDES numeric values must be finite")
            if isinstance(value, bool):
                rendered = "True" if value else "False"
            elif value is None:
                rendered = ""
            else:
                rendered = str(value)
            rendered = _identity(rendered)
            updates.setdefault(section, {})[key] = rendered
            applied.append(f"{section}.{key} (JSON override)")
    return updates, applied


def apply_configuration(settings: Settings) -> list[str]:
    settings.game_ini.parent.mkdir(parents=True, exist_ok=True)
    first_creation = not settings.game_ini.exists()
    updates, applied = build_updates()
    server_updates = updates.get("ServerSetting", {})
    if (
        first_creation
        and server_updates.get("NeedPassword") == "True"
        and not server_updates.get("Password")
    ):
        raise SettingsError(
            "SERVER_PASSWORD or SERVER_PASSWORD_FILE is required when "
            "REQUIRE_PASSWORD=true on first creation"
        )
    if first_creation and "AdminPassword" not in server_updates:
        generated = secrets.token_urlsafe(24)
        server_updates = updates.setdefault("ServerSetting", {})
        server_updates["AdminPassword"] = generated
        settings.state_dir.mkdir(parents=True, exist_ok=True)
        secret_path = settings.state_dir / "generated-admin-password"
        secret_path.write_text(generated + "\n", encoding="utf-8")
        secret_path.chmod(0o600)
        applied.append(
            f"ServerSetting.AdminPassword (generated; stored in {secret_path})"
        )
    merge_ini(settings.game_ini, updates, settings.template_game_ini)
    settings.game_ini.chmod(0o600)
    merge_ini(
        settings.engine_ini,
        {
            "URL": {"Port": str(settings.game_port)},
            "OnlineSubsystemSteam": {"GameServerQueryPort": str(settings.query_port)},
        },
        settings.template_engine_ini,
    )
    settings.engine_ini.chmod(0o640)
    return applied
