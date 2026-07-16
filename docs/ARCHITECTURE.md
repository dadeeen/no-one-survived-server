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

- the CubeCoders Wine base image;
- Valve SteamCMD;
- game server files downloaded anonymously by SteamCMD;
- this repository's Python/shell supervisor.

No game binaries are built into the published image. Pin `BASE_IMAGE` to a tested digest for a controlled release and review base-image updates before deployment.
