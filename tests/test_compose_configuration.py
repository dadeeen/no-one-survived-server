from __future__ import annotations

import re
import unittest
from pathlib import Path

from nos_server.configuration import MAPPINGS


ROOT = Path(__file__).resolve().parents[1]
ENV_KEY_RE = re.compile(r"^      ([A-Z][A-Z0-9_]+):")
INTERPOLATION_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)")

RUNTIME_ENV = {
    "TZ",
    "PUID",
    "PGID",
    "UMASK",
    "RUNTIME_DIR",
    "STATE_FILE",
    "CONTROL_SOCKET",
    "NOSCTL_TIMEOUT_SECONDS",
    "HEALTHCHECK_MAX_HEARTBEAT_AGE",
    "GAME_PORT",
    "QUERY_PORT",
    "MULTIHOME",
    "PREPARE_ON_CONTAINER_START",
    "START_SERVER_ON_CONTAINER_START",
    "UPDATE_ON_CONTAINER_START",
    "UPDATE_ON_WAKE",
    "UPDATE_INTERVAL_SECONDS",
    "UPDATE_RETRY_DELAY_SECONDS",
    "STEAMCMD_TIMEOUT_SECONDS",
    "VALIDATE_ON_UPDATE",
    "START_ON_UPDATE_FAILURE",
    "AUTO_SLEEP_ENABLED",
    "IDLE_TIMEOUT_SECONDS",
    "IDLE_CHECK_INTERVAL_SECONDS",
    "MIN_UPTIME_SECONDS",
    "IDLE_MIN_SUCCESSFUL_QUERIES",
    "A2S_TIMEOUT_SECONDS",
    "A2S_QUERY_HOST",
    "ALLOW_LOG_ONLY_IDLE",
    "WAKE_ON_GAME_PORT",
    "WAKE_ON_QUERY_PORT",
    "WAKE_BIND_ADDRESS",
    "WAKE_SOURCE_POLICY",
    "WAKE_ALLOWED_NETWORKS",
    "WAKE_PACKET_COUNT",
    "WAKE_PACKET_WINDOW_SECONDS",
    "WAKE_ARM_DELAY_SECONDS",
    "WAKE_IGNORE_EMPTY_PACKETS",
    "SERVER_READY_TIMEOUT_SECONDS",
    "SERVER_STOP_TIMEOUT_SECONDS",
    "RESTART_ON_CRASH",
    "CRASH_RESTART_DELAY_SECONDS",
    "MAX_CRASH_RESTARTS",
    "CRASH_RESTART_RESET_SECONDS",
    "EXTRA_SERVER_ARGS",
    "RESET_WINEPREFIX",
    "RESET_WINEPREFIX_ON_VERSION_CHANGE",
    "WINEBOOT_TIMEOUT_SECONDS",
    "WINEDEBUG",
    "USE_XVFB",
    "FIX_PERMISSIONS",
    "GAME_INI_OVERRIDES",
    "GAME_INI_OVERRIDES_FILE",
}
GAME_ENV = set(MAPPINGS) - {"SERVER_PASSWORD", "ADMIN_PASSWORD"}
FULL_REQUIRED_ENV = RUNTIME_ENV | GAME_ENV

SIMPLE_PORTAINER_ENV = {
    "TZ",
    "PUID",
    "PGID",
    "UMASK",
    "USE_XVFB",
    "GAME_PORT",
    "QUERY_PORT",
    "START_SERVER_ON_CONTAINER_START",
    "AUTO_SLEEP_ENABLED",
    "IDLE_TIMEOUT_SECONDS",
    "WAKE_SOURCE_POLICY",
    "WAKE_ALLOWED_NETWORKS",
    "SERVER_NAME",
    "SAVE_NAME",
    "REGION",
    "MAP",
    "MAX_PLAYERS",
    "REQUIRE_PASSWORD",
    "SERVER_PASSWORD_FILE",
    "ADMIN_PASSWORD_FILE",
}


def environment_keys(path: Path) -> set[str]:
    return {
        match.group(1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if (match := ENV_KEY_RE.match(line))
    }


def env_template_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0])
    return keys


def interpolation_keys(path: Path) -> set[str]:
    return set(INTERPOLATION_RE.findall(path.read_text(encoding="utf-8")))


class ComposeConfigurationTests(unittest.TestCase):
    def test_compose_uses_short_env_file(self) -> None:
        path = ROOT / "compose.yaml"
        text = path.read_text(encoding="utf-8")
        self.assertIn("env_file:", text)
        self.assertIn("- .env", text)
        self.assertNotIn("    environment:\n", text)
        self.assertEqual(
            interpolation_keys(path) - env_template_keys(ROOT / ".env.example"),
            set(),
        )

    def test_recommended_stacks_use_smoke_tested_xvfb_path(self) -> None:
        self.assertIn("USE_XVFB=true", (ROOT / ".env.example").read_text())
        self.assertIn(
            "USE_XVFB: ${USE_XVFB:-true}",
            (ROOT / "examples/portainer-stack.yaml").read_text(),
        )

    def test_full_portainer_stack_forwards_all_supported_settings(self) -> None:
        keys = environment_keys(ROOT / "examples/portainer-stack.full.yaml")
        self.assertEqual(FULL_REQUIRED_ENV - keys, set())

    def test_full_environment_templates_cover_all_supported_settings(self) -> None:
        for relative in (
            ".env.full.example",
            "examples/portainer-stack.full.env.example",
        ):
            with self.subTest(path=relative):
                keys = env_template_keys(ROOT / relative)
                self.assertEqual(FULL_REQUIRED_ENV - keys, set())

    def test_simple_portainer_stack_keeps_the_golden_path_small(self) -> None:
        path = ROOT / "examples/portainer-stack.yaml"
        keys = environment_keys(path)
        self.assertEqual(SIMPLE_PORTAINER_ENV - keys, set())
        self.assertLess(len(keys), len(FULL_REQUIRED_ENV))
        self.assertEqual(
            interpolation_keys(path)
            - env_template_keys(ROOT / "examples/portainer-stack.env.example"),
            set(),
        )

    def test_simple_templates_are_subsets_of_full_templates(self) -> None:
        pairs = (
            (".env.example", ".env.full.example"),
            (
                "examples/portainer-stack.env.example",
                "examples/portainer-stack.full.env.example",
            ),
        )
        for simple, full in pairs:
            with self.subTest(simple=simple, full=full):
                self.assertTrue(
                    env_template_keys(ROOT / simple) <= env_template_keys(ROOT / full)
                )

    def test_secret_delivery_is_explicit(self) -> None:
        for relative in (
            "examples/portainer-stack.yaml",
            "examples/portainer-stack.full.yaml",
        ):
            with self.subTest(path=relative):
                keys = environment_keys(ROOT / relative)
                self.assertTrue(
                    {"SERVER_PASSWORD_FILE", "ADMIN_PASSWORD_FILE"}.issubset(keys)
                )
        secret_overlay = (ROOT / "compose.secrets.yaml").read_text(encoding="utf-8")
        self.assertIn("SERVER_PASSWORD_FILE", secret_overlay)
        self.assertIn("ADMIN_PASSWORD_FILE", secret_overlay)


if __name__ == "__main__":
    unittest.main()
