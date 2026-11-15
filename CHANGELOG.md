# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

## [0.1.5] - 2026-11-15

### Fixed

- Roll back interrupted restores after the previous save directory has been moved, retaining recoverable data if rollback fails.
- Reject links and special files in backup sources and store hard-linked files as regular archive members so backups remain restorable.
- Parse backup retention limits as decimal values and reject overflow before pruning archives.
- Prevent runtime state and control paths from overlapping each other or maintenance locks, update markers and generated secrets.
- Reject malformed INI override keys and attempts to override managed settings through Unreal array operators without logging raw invalid input.
- Reject stopped, unknown or malformed supervisor states in health checks and recover heartbeat writes after clock changes.
- Ignore invalid and future Steam update timestamps so they cannot indefinitely postpone updates.
- Close partially initialized UDP wake sockets when listener setup fails.
- Accept decimal user and group IDs with leading zeroes in entrypoint and restore validation.
- Run SteamCMD container checks on compatible Ubuntu runners.

### Security

- Apply available Debian package updates when building the runtime image.
- Scan built and release-candidate images before publication and reject HIGH or CRITICAL vulnerabilities with available fixes.
- Fail vulnerability checks on missing or malformed scan reports and report CRITICAL findings without available fixes for manual assessment.

### Changed

- Update Ruff to 0.17.5, Mypy to 2.4.1 and pinned GitHub Actions.
- Clarify backup recovery, configuration restrictions and wake listener cleanup in English and German documentation.

### Added

- Regression coverage for backup retention and recovery, runtime path collisions, INI overrides, health checks, clock changes and invalid vulnerability scans.

## [0.1.4] - 2026-09-12

### Fixed

- Make save migration transactional so failed copies can be retried without publishing partial saves.
- Serialize game execution, preparation, updates, backups and restores with a shared data lock.
- Clean up SteamCMD and Wine processes after cancellation, heartbeat failures and output-thread startup failures.
- Retain game-process ownership and the data lock until shutdown completes, including failed starts and status-write failures.
- Require repair after an interrupted or failed update unless starting on update failure is explicitly enabled.
- Keep the supervisor available for manual recovery after the crash-restart limit is reached.
- Allow a sleep request to cancel a wake waiting for save maintenance.
- Accept A2S replies only from the configured query endpoint.
- Correct material choices and item/NPC respawn interval validation.
- Keep Compose port overrides consistent between published ports and the container configuration.
- Check every shell script for syntax errors and bind local integration-test ports to loopback.
- Exclude generated integration data from Git and Docker build contexts.

### Changed

- Clarify backup/restore coordination, crash recovery and secret-file ownership in English and German documentation.
- Update Ruff to 0.16.5.

### Added

- Regression coverage for maintenance locking, partial starts, process cleanup and wake cancellation.
- Scheduled container vulnerability reporting with a failure gate for critical vulnerabilities that have an available fix.

## [0.1.3] - 2026-09-03

### Fixed

- Reject destructive persistent-path overlaps, including Wine-prefix and save/server collisions.
- Keep manual and signal wake/sleep requests idempotent across startup, updates and sleep transitions.
- Bind UDP wake sockets before periodic Steam updates so wake packets are not missed during updates.
- Treat startup retry states as retryable in the Linux integration test.
- Honor custom `SAVED_DIR` locations in backup and restore helpers.
- Correct documented container release-tag examples to match published SemVer tags.

## [0.1.0] - 2026-07-17

### Added

- Initial public source release.
- Docker-based runtime for the No One Survived dedicated server using Debian, WineHQ and SteamCMD.
- Automatic server installation and updates.
- Persistent saves and configuration.
- UDP wake-on-packet and A2S-based automatic sleep.
- Manual control through `nosctl` and Unix signals.
- Docker Compose and Portainer deployment examples.
- Backup and restore helpers.
- English and German documentation.
- Unit, image, integration and release workflows.
