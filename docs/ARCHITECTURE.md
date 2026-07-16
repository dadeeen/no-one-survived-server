# Architecture

[Deutsch](ARCHITECTURE.de.md) · [Back to README](../README.md)

The image is a small supervisor around an unmodified SteamCMD installation of the Windows dedicated server.

```text
tini
└── docker-entrypoint (root setup, then gosu)
    └── Python supervisor (unprivileged)
        ├── control Unix socket / nosctl
        ├── SteamCMD updater
        ├── Wine prefix manager
        ├── INI-preserving configuration writer
        ├── sleeping UDP listener
        ├── A2S player monitor
        └── Wine -> WRSHServer.exe
```

The supervisor never calls Docker and does not mount the Docker socket. Resource saving happens by terminating Wine/WRSH while the lightweight supervisor remains active.

## Port ownership invariant

Only one component owns each published UDP port:

- sleeping: `WakeListener`;
- starting/running/idle: `WRSHServer.exe` through Wine.

The listener closes before the server process is started. A short arm delay prevents old packets from immediately waking a server that just stopped.

## Data-loss protections

- saves/configuration are outside the SteamCMD installation directory;
- `/data/server/WRSH/Saved` is a symlink to `/data/saved`;
- an unexpected real `Saved` directory is migrated or moved aside, never silently deleted;
- Wine prefix recreation does not touch saves;
- configuration updates preserve unknown keys and comments;
- update failure prevents startup by default.

## Trust boundaries

The image executes:

- the selected official Debian base image;
- official WineHQ packages;
- Valve's SteamCMD bootstrap;
- game-server files downloaded anonymously by SteamCMD;
- this repository's Python and shell supervisor.

No game binaries are built into the published image. The release workflow records the Debian image digest, exact WineHQ package version and SteamCMD archive SHA-256 used by the tested candidate. Debian repository metadata and transitive APT packages are not frozen through a historical package snapshot, so releases are not claimed to be byte-for-byte reproducible at arbitrary future dates.
