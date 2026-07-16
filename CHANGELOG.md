# Changelog

All notable changes will be documented here.

## [Unreleased]

### Fixed

- Honor `A2S_QUERY_HOST` for idle-player queries, including automatic selection when the variable is empty.
- Reject non-finite numeric timeouts such as `NaN` and infinity.
- Normalize platform overflow from excessively large A2S and `nosctl` socket timeouts into controlled error paths.
- Reject non-finite `GAME_INI_OVERRIDES` values instead of writing `NaN` or infinity to `Game.ini`.
- Preserve wake packet history across listener polling intervals while pruning and bounding tracked source addresses.
- Keep sleeping UDP sockets bound across polling intervals to remove the deliberate close/reopen packet-loss window.
- Honor manual wake requests during the post-stop arm delay without queuing redundant wake requests while the server is active.
- Back off after failed updates instead of retrying every few seconds or exiting into a Docker restart loop.
- Normalize SteamCMD process and operating-system failures to the same recoverable update error path.
- Retry failed initial SteamCMD/Wine preparation inside the supervisor while preserving an observable `ERROR` state.
- Return to sleep after failed wake-time or periodic updates instead of terminating the container.
- Bound Wine-prefix initialization and terminate its process group when `wineboot` exceeds the configured timeout.
- Keep Xvfb alive while explicitly terminating Wine and waiting for its background processes to exit.
- Disable Wine Mono, Gecko and menu-builder helpers by default during headless prefix initialization to prevent hidden first-run prompts from hanging startup.
- Recreate initialized Wine prefixes with no version marker when version-based reset is enabled.
- Remove every empty `LD_LIBRARY_PATH` component instead of implicitly searching the current working directory.
- Keep Wine's `USER` and `LOGNAME` aligned with the actual `nos` runtime identity.
- Prevent `IDLE` status from repeatedly flipping back to `RUNNING` between A2S queries.
- Decode Wine, SteamCMD and game-server output safely with replacement for invalid bytes.
- Clear stale A2S, log-player and retry metadata after recovery or restart.
- Limit SteamCMD update attempts with a configurable total timeout.
- Reject empty password files and require a server password for first-time password-protected configurations.
- Reject relative persistent and runtime paths before canonical resolution.
- Keep `nosctl`, the health check and the supervisor aligned when runtime paths are customized.
- Reject malformed health-state roots, non-finite heartbeats and implausibly future heartbeats instead of reporting them as healthy.
- Bound `nosctl` control-socket operations with a configurable timeout and response-size limit.
- Record control-socket startup failures through the supervisor error state and cleanup path.
- Refuse to unlink an existing regular file, symlink or directory at the configured control-socket path.
- Close a partially initialized control server without calling `shutdown()` before its serving thread starts.
- Canonically validate time-zone paths below `/usr/share/zoneinfo`.
- Preserve runtime ownership during backup/restore and validate restores before replacing live save data.
- Keep the complete advanced environment reference in sync with all supported settings.
- Allow the full graceful-stop escalation path to complete before Docker force-stops the container.
- Continue shutdown escalation through `wineserver` failures and a final process wait timeout.
- Keep locally selected integration-test game and query host ports distinct.
- Install the CA trust store before enabling the WineHQ APT source and fail the build when any configured repository cannot be refreshed.

### Changed

- Added `WAKE_SOURCE_POLICY` with a safe `private` default, strict `allowlist` mode and explicit `any` opt-in for public wake.
- Generalized networking examples for LAN, routed VPN, public IPv4 and DS-Lite/CGNAT deployments.
- Couple the logical `data` volume to the effective Compose/Portainer project name.
- Group routine Dependabot minor and patch updates to reduce PR noise.
- Track Python development dependencies with Dependabot and make `pip-audit` an explicit optional local check.
- Use Python 3.13 as the sole supported and tested Python line, matching the Debian Trixie runtime.
- Suppress rendered Compose models during successful local validation while preserving command failures.
- Use UTC as the neutral default time zone while documenting regional IANA values as examples.
- Neutralize public-facing setup language so the documentation applies to reusable deployments.
- Make container name, image tag, host bind address, stop grace period and log rotation configurable.
- Replace the oversized default Compose and Portainer examples with a short recommended path plus separate full reference variants.
- Move the README quick starts ahead of detailed wake, networking and architecture explanations.
- Replace the CubeCoders AMP runtime base with a first-party image built directly from Debian, WineHQ 11 and Valve SteamCMD.
- Use the Xvfb Wine path in the bundled Compose/Portainer defaults because that path is exercised by the runtime smoke and integration tests.
- Publish images only from valid semantic-version tags or deliberate manual runs, never from every push to `main`.
- Prevent pre-releases from updating `latest` and reject invalid or ambiguous pre-release identifiers.
- Resolve, record and pass the Debian digest, exact WineHQ package version and SteamCMD archive hash through a fresh no-cache candidate build.
- Refuse to overwrite an already published exact release tag and fail closed when registry availability cannot be verified.
- Reuse only the locally exported cache of the smoke-tested release candidate for the final publish build.

### Added

- Lean Debian/WineHQ/SteamCMD runtime without AMP binaries or CubeCoders runtime files.
- Persistent save/configuration separation.
- Configurable UDP wake listener for game and query ports.
- A2S-based idle player detection and automatic graceful sleep.
- Manual control through `nosctl` and Unix signals.
- English and German documentation.
- Unit, build, publish and real-server integration workflows.
- Regression coverage for password safety, runtime paths, bounded wake history, persistent wake sockets, update recovery, control timeouts, deployment-file parity and runtime-image invariants.
- Container smoke coverage for SteamCMD startup, Wine prefix creation, time-zone path rejection and amd64/i386 runtime availability.
- A PowerShell 7 local-CI runner and bilingual maintainer documentation for hosted-Actions outages or quota exhaustion.
