# Local CI from PowerShell

[Deutsch](LOCAL-CI.de.md) · [Back to README](../README.md)

The supplied PowerShell runner reproduces the routine repository checks locally and can optionally perform the large real-server integration test. It is useful for release validation, development checks and situations where hosted CI is unavailable.

## Prerequisites

Required tools and resources:

- PowerShell 7 (`pwsh`);
- Git;
- Docker Desktop or another Docker Engine using Linux containers;
- Docker Buildx and Docker Compose v2;
- enough free disk space and network capacity for Debian, Wine, SteamCMD and the dedicated-server download.

The script tests the current committed `HEAD` in an isolated Git worktree. Commit the changes that should be tested before starting it. Uncommitted working-tree changes are intentionally excluded.

## Routine local CI

From the repository root:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1
```

This runs:

- Ruff format and lint checks targeting Python 3.13;
- strict Mypy checks targeting Python 3.13;
- the complete unit-test suite on Python 3.13;
- Python bytecode compilation;
- Linux shell syntax and behavior tests;
- all supported Compose and Portainer model combinations, including the secrets overlay;
- a fresh `linux/amd64` image build;
- the Wine, Xvfb and SteamCMD runtime smoke test;
- image size and recorded upstream-version output.

Python 3.13 is the only supported Python line because it matches the Debian Trixie container runtime. Python 3.14 is deliberately not claimed or tested for this container-specific project.

The temporary worktree is removed automatically. The built image remains available locally as `no-one-survived-server:ci` for inspection.

## Clean release-style build

Use a build without the local Docker layer cache for release candidates:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1 -NoCache
```

This is slower but catches assumptions hidden by a previously successful layer.

## Real dedicated-server integration

The integration test downloads several gigabytes and can take up to roughly 110 minutes. It installs the current dedicated server, creates the Wine prefix, waits for the sleeping state, sends a UDP wake packet, verifies startup and requests a graceful return to sleep:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1 -NoCache -Integration
```

For the strongest check, also require a successful real Steam A2S response:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1 -NoCache -FullRuntime
```

`-FullRuntime` automatically enables the integration test.

## Optional switches

| Switch | Meaning |
|---|---|
| `-NoCache` | Build the image without Docker layer-cache reuse. |
| `-Integration` | Download and start the real dedicated server. |
| `-FullRuntime` | Run integration and require a real A2S response. |
| `-Audit` | Run an additional `pip-audit` check for the pinned development tools. |
| `-KeepWorktree` | Retain the isolated temporary worktree for debugging. |

The application has no third-party Python runtime dependencies. The optional audit therefore covers development tools rather than the shipped Wine/SteamCMD image and is not part of the normal local gate.

A failed command terminates the run with a non-zero exit. The integration container and its temporary Docker volume are removed in the cleanup path, including after most failures.

## Release workflow

Published images are created from a valid `vMAJOR.MINOR.PATCH` tag, an optional valid SemVer pre-release tag or a deliberate manual workflow run. Before pushing an image, the release workflow:

1. validates the release tag and prevents a pre-release from moving `latest`;
2. verifies that an exact tag is absent and fails closed when the registry cannot answer reliably;
3. resolves the immutable Debian image digest;
4. builds a no-cache discovery image;
5. records the exact WineHQ package version and SteamCMD archive SHA-256;
6. creates a second no-cache candidate with those primary inputs pinned and the final version metadata;
7. runs the runtime smoke test against that candidate;
8. exports the candidate's local BuildKit cache and permits the publish build to reuse only that tested cache;
9. publishes SBOM and provenance information with the image.

These pins make the primary upstream identities explicit. Debian repository metadata and transitive APT packages are not frozen through a historical package snapshot, so the process should not be described as byte-for-byte reproducible across arbitrary future dates.
