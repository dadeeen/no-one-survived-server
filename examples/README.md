# Recommended Portainer stack

[Deutsch](README.de.md) · [Portainer documentation](../docs/PORTAINER.md)

The recommended Portainer pair is intentionally short:

- [`portainer-stack.yaml`](portainer-stack.yaml)
- [`portainer-stack.env.example`](portainer-stack.env.example)

It includes the persistent data volume, read-only password files, safe wake/sleep defaults, a sufficient stop grace period, log rotation and `no-new-privileges`. The advanced pair exposes every supported setting:

- [`portainer-stack.full.yaml`](portainer-stack.full.yaml)
- [`portainer-stack.full.env.example`](portainer-stack.full.env.example)

## 1. Create password files

The examples use UID and GID `1000`. Adjust both the commands and stack variables when using different IDs.

```bash
sudo install -d -m 0750 -o 1000 -g 1000 /opt/games/no-one-survived/secrets

printf '%s\n' 'choose-a-strong-server-password' \
  | sudo tee /opt/games/no-one-survived/secrets/server_password.txt >/dev/null
printf '%s\n' 'choose-a-long-random-admin-password' \
  | sudo tee /opt/games/no-one-survived/secrets/admin_password.txt >/dev/null

sudo chown 1000:1000 /opt/games/no-one-survived/secrets/*.txt
sudo chmod 0400 /opt/games/no-one-survived/secrets/*.txt
```

Both files must contain a non-empty value. Empty secret files are rejected.

## 2. Create the stack

1. Open **Stacks → Add stack → Web editor** and paste `portainer-stack.yaml`.
2. Choose a unique, permanent Portainer stack name.
3. Import `portainer-stack.env.example` under **Environment variables**.
4. For a private GHCR package, add `ghcr.io` as a registry with a token containing `read:packages`.
5. Deploy and follow the container log.

The logical volume is called `data` in the stack. Compose or Portainer prefixes it with the effective project/stack name. With the default name, the resulting Docker volume is normally `no-one-survived_data`.

**Keep the effective project/stack name stable after the first deployment.** Renaming creates a new empty volume; the old volume remains available but is no longer attached automatically.

## 3. What happens next

The first start downloads the dedicated server and prepares Wine. The container then remains in `SLEEPING` until an allowed UDP packet wakes the game server.

```bash
docker exec no-one-survived nosctl status
docker logs -f no-one-survived
```

The first connection packet only wakes the server. Retry the favorite or direct connection after startup.

## Most common adjustments

```env
SERVER_NAME=My NoS Server
MAX_PLAYERS=8
TZ=Europe/Berlin
IDLE_TIMEOUT_SECONDS=3600
WAKE_SOURCE_POLICY=private
```

For a strict list of trusted networks:

```env
WAKE_SOURCE_POLICY=allowlist
WAKE_ALLOWED_NETWORKS=192.168.10.0/24,10.50.0.0/24
```

Use `WAKE_SOURCE_POLICY=any` only deliberately for publicly reachable UDP ports.

## Advanced configuration

Use the `.full` stack and environment template when update scheduling, A2S tuning, Wine compatibility, crash recovery or extended game settings must be visible in Portainer. Both simple and full variants use the same persistent volume and password-file layout.

## Second server instance

The Portainer project/stack name, container name and host ports must be unique:

```env
STACK_NAME=no-one-survived-2
CONTAINER_NAME=no-one-survived-2
GAME_PORT=7778
QUERY_PORT=27016
```

Compose normally creates `no-one-survived-2_data` for the second stack.

## Volume and image maintenance

```bash
docker volume inspect no-one-survived_data
docker volume ls --filter name=no-one-survived
```

The volume remains when the container is recreated or updated. It is deleted only when explicitly removed, for example with `docker volume rm`, `docker compose down -v`, or the corresponding Portainer action. Back up `/data/saved` outside the Docker host.

`IMAGE_TAG=latest` is convenient during development. For stable operation, use a tested release tag such as `v0.1.0`.
