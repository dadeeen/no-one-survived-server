# Portainer stack example

[Deutsch](README.de.md) · [Portainer documentation](../docs/PORTAINER.md) · [Configuration reference](../docs/CONFIGURATION.md)

[`portainer-stack.yaml`](portainer-stack.yaml) is the only Portainer example. It is ready to paste into Portainer's web editor and contains sensible defaults for a normal installation. No separate environment file is required.

## 1. Create password files

The example uses UID and GID `1000`. Adjust both the commands and the `PUID`/`PGID` values in the stack when using different IDs.

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

1. Open **Stacks → Add stack → Web editor**.
2. Paste [`portainer-stack.yaml`](portainer-stack.yaml).
3. Edit the visible values directly in the YAML, especially the image tag, time zone, server name and player limit.
4. Choose a unique, permanent Portainer stack name.
5. Deploy and follow the container log.

For a private GHCR package, add `ghcr.io` as a registry with a token containing `read:packages`. Public packages do not require registry credentials.

The logical volume is called `data`. Portainer prefixes it with the stack name, so a stack called `no-one-survived` normally creates `no-one-survived_data`.

**Keep the stack name stable after the first deployment.** Renaming creates a new empty volume; the old volume remains available but is no longer attached automatically.

## 3. What happens next

The first start downloads the dedicated server and prepares Wine. The container then remains in `SLEEPING` until an allowed UDP packet wakes the game server.

```bash
docker exec no-one-survived nosctl status
docker logs -f no-one-survived
```

The first connection packet only wakes the server. Retry the favorite or direct connection after startup.

## Common adjustments

Edit the values directly below `environment:`:

```yaml
environment:
  TZ: Europe/Berlin
  SERVER_NAME: My NoS Server
  MAX_PLAYERS: "8"
  IDLE_TIMEOUT_SECONDS: "3600"
  WAKE_SOURCE_POLICY: private
```

For a strict list of trusted networks:

```yaml
environment:
  WAKE_SOURCE_POLICY: allowlist
  WAKE_ALLOWED_NETWORKS: 192.168.10.0/24,10.50.0.0/24
```

Use `WAKE_SOURCE_POLICY: any` only deliberately for publicly reachable UDP ports. Every supported optional variable is described in the [configuration reference](../docs/CONFIGURATION.md); add only the variables you need to the existing `environment:` block.

## Second server instance

Choose another permanent Portainer stack name, then change the container name and host-side ports:

```yaml
container_name: no-one-survived-2
ports:
  - "7778:7777/udp"
  - "27016:27015/udp"
```

The internal ports remain `7777` and `27015`. Portainer automatically gives the second stack its own named volume.

## Volume and image maintenance

```bash
docker volume inspect no-one-survived_data
docker volume ls --filter name=no-one-survived
```

The volume remains when the container is recreated or updated. It is deleted only when explicitly removed, for example with `docker volume rm`, `docker compose down -v`, or the corresponding Portainer action. Back up `/data/saved` outside the Docker host.

The example uses `latest` for convenience. For stable operation, replace it in the `image:` line with a tested release tag such as `v0.1.0`.
