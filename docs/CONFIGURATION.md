# Configuration reference

[Deutsch](CONFIGURATION.de.md) · [Back to README](../README.md)

Values are supplied through environment variables. Boolean values accept `true/false`, `1/0`, `yes/no` and `on/off`. The recommended `.env.example` and copy-and-paste Portainer stack include the common settings needed for a normal installation. Add any other variable below to `.env` for Docker Compose or to the existing `environment:` block in Portainer.

## Docker Compose settings

| Variable | Default | Meaning |
|---|---:|---|
| `TZ` | `UTC` | Container time zone, for example `Europe/Berlin`. |
| `STACK_NAME` | `no-one-survived` | Effective Compose project name and prefix of the `data` volume. Keep stable after first deployment. |
| `IMAGE_TAG` | `latest` | GHCR image tag. Prefer a tested release tag for stable operation. |
| `CONTAINER_NAME` | `no-one-survived` | Explicit container name. Must differ between instances. |
| `HOST_BIND_ADDRESS` | `0.0.0.0` | Host address used for the two published UDP ports. |
| `STOP_GRACE_PERIOD` | `180s` | Docker stop grace period. This exceeds the supervisor's full graceful-stop escalation path. |
| `LOG_MAX_SIZE` / `LOG_MAX_FILES` | `10m` / `3` | Docker `json-file` log rotation. |

In Portainer, edit the equivalent image, container, port, stop-grace and logging values directly in `examples/portainer-stack.yaml`. The Portainer stack name determines the named-volume prefix.

## Lifecycle and updates

| Variable | Default | Meaning |
|---|---:|---|
| `PREPARE_ON_CONTAINER_START` | `true` | Initialize SteamCMD/Wine/configuration before entering the initial state. |
| `START_SERVER_ON_CONTAINER_START` | `false` in `compose.yaml` | Start the game server immediately. When false, enter UDP wake mode after preparation. |
| `UPDATE_ON_CONTAINER_START` | `true` | Run SteamCMD during container startup. A missing server is always installed. |
| `UPDATE_ON_WAKE` | `false` | Run SteamCMD before every wake. This increases wake latency. |
| `UPDATE_INTERVAL_SECONDS` | `0` | Periodic update interval while sleeping. `0` disables it. |
| `UPDATE_RETRY_DELAY_SECONDS` | `900` | Delay before retrying a failed initial preparation or periodic update. Initial preparation remains in the container and retries instead of causing a Docker restart loop. |
| `STEAMCMD_TIMEOUT_SECONDS` | `3600` | Maximum total runtime of one SteamCMD update attempt. |
| `VALIDATE_ON_UPDATE` | `false` | Add `validate` to SteamCMD app update. Use for repair, not every normal start. |
| `START_ON_UPDATE_FAILURE` | `false` | Start existing server files when a non-required update fails. A first installation still fails closed and retries after `UPDATE_RETRY_DELAY_SECONDS`. |
| `RESTART_ON_CRASH` | `true` | Restart an unexpectedly exited game server. |
| `CRASH_RESTART_DELAY_SECONDS` | `15` | Delay before a crash restart. |
| `MAX_CRASH_RESTARTS` | `3` | Maximum consecutive automatic crash restarts. |
| `CRASH_RESTART_RESET_SECONDS` | `600` | Reset the crash counter after this stable runtime; `0` disables reset. |

During an initial SteamCMD or Wine preparation failure, the supervisor writes `ERROR` state information, stays alive and retries after the configured delay. This keeps `restart: unless-stopped` from turning a transient upstream outage into a rapid container restart loop. Configuration errors still fail immediately and must be corrected before recreating or restarting the container.

## Wake-on-packet

| Variable | Default | Meaning |
|---|---:|---|
| `WAKE_ON_GAME_PORT` | `true` | Listen on `GAME_PORT` while sleeping. |
| `WAKE_ON_QUERY_PORT` | `true` | Listen on `QUERY_PORT` while sleeping. |
| `WAKE_BIND_ADDRESS` | `0.0.0.0` | Local IPv4 address used by the sleeping listener. |
| `WAKE_SOURCE_POLICY` | `private` | `private`, `allowlist` or `any`; controls which IPv4 sources may wake the server. |
| `WAKE_ALLOWED_NETWORKS` | empty | Optional comma-separated IPv4 CIDRs. Added to `private`, required for `allowlist`, ignored for access decisions with `any`. |
| `WAKE_PACKET_COUNT` | `1` | Number of packets from one source IP required inside the packet window. Increase to reduce accidental wakes. |
| `WAKE_PACKET_WINDOW_SECONDS` | `5` | Time window for `WAKE_PACKET_COUNT`. |
| `WAKE_ARM_DELAY_SECONDS` | `5` | Delay after shutdown before wake packets are accepted, preventing immediate re-wake from stale traffic. |
| `WAKE_IGNORE_EMPTY_PACKETS` | `true` | Ignore zero-length UDP datagrams. |

The first accepted packet wakes the server but is not replayed. The client must retry after startup. Packet history is time-pruned and capped to avoid unbounded growth from many source addresses. While the server sleeps, the listener keeps its UDP sockets bound across polling intervals; there is no deliberate five-second close/reopen window.

Recommended default:

```env
WAKE_SOURCE_POLICY=private
WAKE_ALLOWED_NETWORKS=
WAKE_PACKET_COUNT=1
```

`private` includes RFC1918 LAN ranges, Docker bridge ranges, `100.64.0.0/10` for overlay networks and loopback. Use `allowlist` for strict explicit CIDRs. Use `any` only when public wake is intentional. This policy controls wake only and does not replace firewall or game-password access control.

For manual-only wake, set both wake-port variables to `false` and use `nosctl wake` or `SIGUSR1`. A wake request while the server is already `STARTING`, `RUNNING` or `IDLE` returns “server already active” and is not queued for a later restart.

## Automatic sleep and player detection

| Variable | Default | Meaning |
|---|---:|---|
| `AUTO_SLEEP_ENABLED` | `true` | Enable automatic graceful shutdown with zero players. |
| `IDLE_TIMEOUT_SECONDS` | `3600` | Required continuous idle period. Minimum 60 seconds. |
| `IDLE_CHECK_INTERVAL_SECONDS` | `30` | Interval between Steam A2S information queries. |
| `MIN_UPTIME_SECONDS` | `900` | Minimum server uptime before automatic sleep is allowed. |
| `IDLE_MIN_SUCCESSFUL_QUERIES` | `3` | Minimum consecutive successful zero-player A2S responses before sleep. |
| `A2S_TIMEOUT_SECONDS` | `2` | Timeout for the local A2S query. Must be a positive finite number. |
| `A2S_QUERY_HOST` | automatic | Empty selects `127.0.0.1` when `MULTIHOME=0.0.0.0`, otherwise the MultiHome address. |
| `ALLOW_LOG_ONLY_IDLE` | `false` | Permit log join/leave tracking when A2S never works. This is less safe and disabled by default. |

The default behavior is deliberately conservative: an A2S failure clears the idle timer, so the container does not stop a server whose player count cannot be confirmed.

## Ports and process

| Variable | Default | Meaning |
|---|---:|---|
| `GAME_PORT` | `7777` | UDP game port. |
| `QUERY_PORT` | `27015` | UDP Steam query port and A2S player-count source. |
| `MULTIHOME` | `0.0.0.0` | Address passed to `-MultiHome`. |
| `SERVER_READY_TIMEOUT_SECONDS` | `300` | Time after which a live process is treated as running even if the known readiness log line changed. |
| `SERVER_STOP_TIMEOUT_SECONDS` | `90` | Grace period after SIGINT before escalation. |
| `EXTRA_SERVER_ARGS` | empty | Extra arguments parsed with shell-like quoting and appended without using a shell. |
| `USE_XVFB` | `true` in supplied examples | Prefix Wine commands with `xvfb-run -a`. This is the default deployment path and the path exercised by the runtime smoke test. Set `false` only after validating direct headless Wine on the target host. |

The container publishes both ports as UDP. Host and container port numbers should remain identical because the generated `Engine.ini` and command line use the same values.

## Game configuration

Only non-empty game-setting variables overwrite values in `Game.ini`. Empty values are treated as unset, so manually maintained values are preserved. The supplied examples provide common initial values. Add any variable listed below to `.env` or to Portainer's `environment:` block when it should be managed by the container. Unknown sections, unknown keys and comments are preserved.

| Variable | INI key | Accepted values |
|---|---|---|
| `SERVER_NAME` | `ServerSetting.ServerName` | text |
| `SAVE_NAME` | `ServerSetting.SaveName` | text |
| `REQUIRE_PASSWORD` | `ServerSetting.NeedPassword` | boolean |
| `SERVER_PASSWORD` / `_FILE` | `ServerSetting.Password` | text/secret file |
| `ADMIN_PASSWORD` / `_FILE` | `ServerSetting.AdminPassword` | text/secret file |
| `MAP` | `ServerSetting.OpenMap` | normally `Map01` or `Map02` |
| `MAX_PLAYERS` | `ServerSetting.MaxPlayers` | 2–50 |
| `REGION` | `ServerSetting.Region` | e.g. `EU`, `NA`, `AS`, `AF`, `OC`, `SA`, `All` |
| `ZOMBIES_PER_PLAYER` | `ServerSetting.NumOfZombieSpawn` | 25–100 |
| `PVP` | `GameSettings.PVP` | boolean |
| `ZOMBIE_ATTACK` | `GameSettings.ZombieAttack` | boolean |
| `ZOMBIE_ATTACK_DAY` | `GameSettings.ZombieAttackDay` | 1–30 |
| `ATTACK_ZOMBIE_NUM` | `GameSettings.AttackZombieNum` | 1–5 |
| `ZOMBIE_NUM` | `GameSettings.ZombieNum` | 1–3 |
| `RUN_ZOMBIE_PERCENT` | `GameSettings.RunZombiePercent` | 0–1 |
| `ZOMBIE_STRENGTH` | `GameSettings.ZombieStreng` | 0–3 |
| `SPECIAL_ZOMBIE` | `GameSettings.SpecialZombie` | boolean |
| `YEAR_DAYS` | `GameSettings.YearDay` | 1–365 |
| `DAY_LENGTH` | `GameSettings.DayLength` | 1–240 |
| `PERMADEATH` | `GameSettings.PermanentDead` | boolean |
| `MATERIAL_AMOUNT` | `GameSettings.MaterialNum` | 0.1–10 |
| `ITEM_SPAWN` | `GameSettings.ItemSpawn` | 0.1–10 |
| `VIRUS_FATALITY_RATE` | `GameSettings.VirusFatalityRate` | 0–1 |
| `NOVICE_GIFT_BAG` | `GameSettings.GiftBagForNovices` | boolean |
| `NPC_ITEM_SPAWN` | `GameSettings.NPCItemSpawn` | 0.1–10 |

Future or uncommon settings can be supplied through `GAME_INI_OVERRIDES` as JSON:

```env
GAME_INI_OVERRIDES={"ServerSetting":{"FutureSetting":"Value"},"GameSettings":{"AnotherValue":2}}
```

For complex or sensitive JSON use `GAME_INI_OVERRIDES_FILE`. The referenced file must be mounted into the container and readable by the configured `PUID`; the supplied examples do not automatically mount arbitrary override files.

### Passwords

Prefer Docker secrets:

```bash
docker compose -f compose.yaml -f compose.secrets.yaml up -d
```

Empty direct password variables are treated as unset so optional Compose interpolation remains safe. Empty password files are rejected. On first creation, `REQUIRE_PASSWORD=true` requires a non-empty `SERVER_PASSWORD` or `SERVER_PASSWORD_FILE`. If no admin password is supplied when `Game.ini` is first created, a random one is generated and saved with mode `0600` at `/data/state/generated-admin-password`.

## Wine and persistent paths

| Variable | Default | Meaning |
|---|---:|---|
| `DATA_DIR` | `/data` | Root of persistent data. |
| `SERVER_DIR` | `/data/server` | SteamCMD installation directory. |
| `SAVED_DIR` | `/data/saved` | Persistent WRSH `Saved` directory. |
| `STATE_DIR` | `/data/state` | Persistent update, Wine-version and generated-secret markers. |
| `STEAMCMD_DIR` | `/data/steamcmd` | Writable SteamCMD installation. |
| `WINEPREFIX` | `/data/wine` | Persistent 64-bit Wine prefix. |
| `RESET_WINEPREFIX` | `false` | Delete/recreate the prefix on this start. |
| `RESET_WINEPREFIX_ON_VERSION_CHANGE` | `true` | Recreate the prefix when `wine --version` changed. Saves are separate and retained. |
| `WINEBOOT_TIMEOUT_SECONDS` | `600` | Maximum time for creation of a fresh Wine prefix before its process group is terminated and preparation enters retry backoff. |
| `WINEDEBUG` | `-all` | Wine debug setting. |
| `PUID` / `PGID` | `1000` | Runtime user/group IDs. |
| `UMASK` | `0027` | Runtime file creation mask; `Game.ini` is additionally forced to `0600`. |
| `FIX_PERMISSIONS` | `true` | Apply recursive ownership once per UID/GID pair using a marker in `/data`. Accepts the same boolean spellings as the Python settings. |

The supplied Compose and Portainer stacks deliberately mount the named volume at `/data` and do not expose alternate persistent-root layouts. `DATA_DIR`, `SERVER_DIR`, `SAVED_DIR`, `STATE_DIR`, `STEAMCMD_DIR` and `WINEPREFIX` remain available for custom `docker run` or derived-image integrations. Every persistent path must be absolute and remain below `DATA_DIR`.

## Control and health

| Variable | Default | Meaning |
|---|---:|---|
| `RUNTIME_DIR` | `/run/nos` | Ephemeral runtime directory. Must be absolute. |
| `STATE_FILE` | `<RUNTIME_DIR>/state.json` | Optional absolute supervisor state-file override. Empty keeps the derived default. |
| `CONTROL_SOCKET` | `<RUNTIME_DIR>/control.sock` | Optional absolute control-socket override. Empty keeps the derived default. An existing non-socket path is never removed. |
| `NOSCTL_TIMEOUT_SECONDS` | `5` | Maximum connect/read time for one `nosctl` request. Must be a positive finite number. |
| `HEALTHCHECK_MAX_HEARTBEAT_AGE` | `600` | Maximum heartbeat age in seconds before the container becomes unhealthy. |

```bash
docker exec no-one-survived nosctl status
docker exec no-one-survived nosctl wake
docker exec no-one-survived nosctl sleep
```

The health check considers `SLEEPING` healthy. It fails for `ERROR`, a missing/invalid state file, invalid heartbeat configuration or a stale heartbeat. Control-socket startup errors are recorded as supervisor `ERROR` state instead of escaping before cleanup.
