# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

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
