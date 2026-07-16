# No One Survived Dedicated Server — Docker

[Deutsch](README.de.md) · [Configuration](docs/CONFIGURATION.md) · [Wake & sleep](docs/WAKE-AND-SLEEP.md) · [Networking](docs/NETWORKING.md) · [Portainer](docs/PORTAINER.md) · [Backup](docs/BACKUP-RESTORE.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Local CI](docs/LOCAL-CI.md) · [Architecture](docs/ARCHITECTURE.md) · [Upstream](docs/UPSTREAM.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md)

A Wine/SteamCMD container for the **No One Survived** dedicated server. It installs and updates the server automatically, keeps saves persistent, wakes on an allowed UDP packet and shuts the game process down after a configurable idle period.

> This project is unofficial and is not affiliated with Cat Play Studio, Steam, Valve or CubeCoders. It does not redistribute game or dedicated-server files.
>
> **Validation status**
>
> - Passed locally: installation and update, Wine startup, A2S response, UDP wake and graceful sleep.
> - Not yet fully validated: long-term operation, save persistence across game updates and public reachability across different network types.

## Quick start with Docker Compose

```bash
git clone https://github.com/dadeeen/no-one-survived-server.git
cd no-one-survived-server

cp .env.example .env

install -d -m 0700 secrets
printf '%s\n' 'choose-a-server-password' > secrets/server_password.txt
printf '%s\n' 'choose-a-long-random-admin-password' > secrets/admin_password.txt
chmod 0600 secrets/*.txt

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
3. Import [`examples/portainer-stack.env.example`](examples/portainer-stack.env.example) under **Environment variables**.
4. Choose a permanent stack name and deploy.

The recommended files expose only the settings needed for a normal installation. Advanced deployments can use [`examples/portainer-stack.full.yaml`](examples/portainer-stack.full.yaml) with [`examples/portainer-stack.full.env.example`](examples/portainer-stack.full.env.example).

## Most common settings

Edit `.env` before deployment or recreate the container after changing it:

```env
SERVER_NAME=My NoS Server
MAX_PLAYERS=8
TZ=Europe/Berlin
IDLE_TIMEOUT_SECONDS=3600
WAKE_SOURCE_POLICY=private
```

The recommended `.env.example` covers the normal path, including the smoke-tested Xvfb Wine mode. Copy `.env.full.example` instead when every supported option should be visible. The complete descriptions are in [Configuration](docs/CONFIGURATION.md).

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

`WAKE_SOURCE_POLICY` controls only who may wake a sleeping server; it is not a firewall for the running server. Deployment examples and public-access considerations are documented in [Networking](docs/NETWORKING.md).

> **Public IPv4 / DS-Lite:** If the server appears in the in-game list but joining stalls or times out, verify that the internet connection has a dedicated public IPv4 address. With DS-Lite/CGNAT, outbound Steam registration may succeed while unsolicited inbound UDP traffic to ports `7777` and `27015` cannot be forwarded through the provider-side NAT. Router port forwarding alone is then insufficient; a public IPv4/dual-stack option or an externally reachable tunnel or relay may be required. This behavior has not yet been conclusively confirmed for No One Survived and should be treated as a troubleshooting lead, not a confirmed game limitation.

## Build locally

```bash
cp .env.example .env
docker compose -f compose.yaml -f compose.build.yaml build
```

The runtime is built directly from the official `debian:trixie-slim` image, official WineHQ stable packages from the selected Wine 11 release line and Valve's SteamCMD bootstrap. It includes no AMP or CubeCoders runtime files. Release publication records and pins the Debian digest, WineHQ package version and SteamCMD archive hash used by the tested candidate; transitive APT packages are not frozen through a historical package snapshot.

## Validation status

The repository includes tests for UDP wake, CIDR policies, A2S parsing, INI-preserving configuration updates, secret validation, simple/full deployment-file parity, update scheduling, backup/restore safety and runtime-image invariants. The image build also smoke-tests amd64/i386 support, required runtime commands, SteamCMD startup and creation of a fresh Wine prefix.

When hosted Actions are unavailable, the complete routine check can be run from PowerShell with:

```powershell
pwsh -NoProfile -File ./scripts/run-local-ci.ps1
```

The optional real-server and A2S checks are documented under [Local CI](docs/LOCAL-CI.md). A production release should not be treated as validated until the current game build has passed startup, A2S, graceful-stop and save-persistence checks on a Docker host.

## License

Project code is released under the MIT License. Debian, Wine, SteamCMD and the game server retain their own licenses and terms.
