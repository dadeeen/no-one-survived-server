# No One Survived Dedicated Server — Docker

[Deutsch](README.de.md) · [Configuration](docs/CONFIGURATION.md) · [Portainer](docs/PORTAINER.md) · [Networking](docs/NETWORKING.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

A Wine/SteamCMD container for the **No One Survived** dedicated server. It installs and updates the server automatically, keeps saves persistent, wakes on an allowed UDP packet and shuts the game process down after a configurable idle period.

> This project is unofficial and is not affiliated with Cat Play Studio, Steam or Valve. It does not redistribute game or dedicated-server files.

## Quick start with Docker Compose

```bash
git clone https://github.com/dadeeen/no-one-survived-server.git
cd no-one-survived-server

cp .env.example .env

install -d -m 0700 secrets
printf '%s\n' 'choose-a-server-password' > secrets/server_password.txt
printf '%s\n' 'choose-a-long-random-admin-password' > secrets/admin_password.txt
chmod 0600 secrets/*.txt
# Match PUID:PGID in .env (defaults below); root can omit sudo.
sudo chown 1000:1000 secrets/*.txt

docker compose -f compose.yaml -f compose.secrets.yaml up -d
docker compose logs -f
```

The first start downloads the Windows dedicated server and prepares Wine. When `nosctl status` reports `SLEEPING`, setup is complete:

```bash
docker exec no-one-survived nosctl status
```

The first connection packet wakes the server but cannot complete the join. Retry the favorite or direct connection after the game server has started, usually after roughly 30–90 seconds.

## Quick start with Portainer

1. Create the two password files as shown in the [Portainer example guide](examples/README.md#1-create-password-files).
2. Open **Stacks → Add stack → Web editor** and paste [`examples/portainer-stack.yaml`](examples/portainer-stack.yaml).
3. Edit the visible values directly in the YAML.
4. Choose a permanent stack name and deploy.

No separate environment file is required. The stack contains the common settings for a normal installation; add optional variables from [Configuration](docs/CONFIGURATION.md) only when needed.

## Most common settings

For Docker Compose, edit `.env` before deployment. In Portainer, edit the same values directly below `environment:` in the stack:

```env
SERVER_NAME=My NoS Server
MAX_PLAYERS=8
TZ=Europe/Berlin
IDLE_TIMEOUT_SECONDS=3600
WAKE_SOURCE_POLICY=private
```

The recommended `.env.example` and Portainer stack cover the normal path, including the smoke-tested Xvfb Wine mode. Every supported optional setting is described in [Configuration](docs/CONFIGURATION.md).

## How wake-on-packet works

While sleeping, the container remains running but `WRSHServer.exe` and Wine are stopped. A small Python listener owns UDP ports `7777` and/or `27015`. When an allowed packet arrives, the listener closes its sockets and starts the game server.

After the server reports zero players for the configured idle period, it shuts down cleanly and re-arms the listener. The default `private` policy accepts common private LAN, container and routed VPN ranges while rejecting public IPv4 wake packets. Use `allowlist` for explicit CIDRs or `any` only for deliberately public wake.

## Useful commands

```bash
# State and player count
docker exec no-one-survived nosctl status

# Manual wake
docker exec no-one-survived nosctl wake

# Gracefully put the game server to sleep
docker exec no-one-survived nosctl sleep

# Container logs
docker compose logs -f
```

Signals are also available:

```bash
docker kill --signal SIGUSR1 no-one-survived  # wake
docker kill --signal SIGUSR2 no-one-survived  # sleep
```

## Persistent layout

```text
/data/
├── server/       SteamCMD installation of the dedicated server
├── saved/        saves, logs, Game.ini and Engine.ini
├── wine/         Wine prefix (re-creatable)
├── steamcmd/     self-updating SteamCMD installation
├── state/        update/Wine markers and generated admin password
├── home/         runtime home directory
└── backups/      optional local backup archives
```

`/data/server/WRSH/Saved` is linked to `/data/saved`, so server updates and reinstallations do not replace the persistent save directory. Back up `/data/saved` outside the Docker host.

## Networking

Clients connect to a reachable address of the Docker host, VM or container host. Routed networks usually require direct IP or a Steam favorite because broadcast discovery does not normally cross routers.

`WAKE_SOURCE_POLICY` controls who can wake the server. The firewall and server password control access once it is running.

If the server is listed but players cannot join over the internet, [DS-Lite or CGNAT](docs/NETWORKING.md#ds-lite-and-cgnat) may be blocking inbound IPv4 connections.

## Build locally

```bash
cp .env.example .env
docker compose -f compose.yaml -f compose.build.yaml build
```

The runtime is built directly from the official `debian:trixie-slim` image, official WineHQ stable packages from the selected Wine 11 release line and Valve's SteamCMD bootstrap. It does not use a third-party game-server control panel or prebuilt game-server runtime. Release publication pins the Debian digest and WineHQ package version and records the SteamCMD archive hash used by the tested candidate for traceability; transitive APT packages are not frozen through a historical package snapshot.

## Validation status

Local tests with the dedicated server confirmed installation, updates, Wine startup, UDP wake, A2S responses and graceful sleep. Long-term operation, save persistence across game updates and public reachability across different network types still need testing.

## Documentation

Additional user guides: [Wake & sleep](docs/WAKE-AND-SLEEP.md) and [Backup and restore](docs/BACKUP-RESTORE.md).

Project and maintainer documentation: [Local CI](docs/LOCAL-CI.md), [Architecture](docs/ARCHITECTURE.md), [Upstream compatibility](docs/UPSTREAM.md), [Changelog](CHANGELOG.md) and [Security policy](SECURITY.md).

## License

Project code is released under the MIT License. Debian, Wine, SteamCMD and the game server retain their own licenses and terms.
