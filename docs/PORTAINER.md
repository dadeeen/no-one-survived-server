# Portainer deployment

[Deutsch](PORTAINER.de.md) · [Back to README](../README.md) · [Configuration reference](CONFIGURATION.md)

## Create password files on the Docker host

Before the first deployment, replace both example passwords with your own non-empty values. If the stack uses different `PUID` and `PGID` values, use the same IDs in these commands. The stack mounts both files read-only.

```bash
sudo install -d -m 0750 -o 1000 -g 1000 /opt/games/no-one-survived/secrets

printf '%s\n' 'choose-a-strong-server-password' \
  | sudo tee /opt/games/no-one-survived/secrets/server_password.txt >/dev/null
printf '%s\n' 'choose-a-long-random-admin-password' \
  | sudo tee /opt/games/no-one-survived/secrets/admin_password.txt >/dev/null

sudo chown 1000:1000 /opt/games/no-one-survived/secrets/*.txt
sudo chmod 0400 /opt/games/no-one-survived/secrets/*.txt
```

## Deploy the stack

For a private GHCR package, add `ghcr.io` as a registry before deployment. Sign in with your GitHub username and a token with `read:packages`. Public packages allow anonymous pulls.

1. In Portainer, open **Stacks → Add stack → Web editor** and paste the [stack template](../examples/portainer-stack.yaml).
2. Choose a permanent stack name. With the name `no-one-survived`, the data lives in the volume `no-one-survived_data`. Renaming the stack mounts a new, empty volume. The original volume remains available.
3. Under `environment:`, set the time zone, server name and player limit. Quote numeric and boolean values. To pin a version, replace `latest` in the `image:` line with your chosen release tag. This stack works without a separate `.env` file.
4. Select **Deploy the stack** and open the container log. On first startup, SteamCMD downloads the dedicated server and Wine prepares it to run.

## Check the first start

```bash
docker logs --tail 100 no-one-survived
docker exec no-one-survived nosctl status
```

At `SLEEPING`, the server is ready to wake and Portainer reports the container as healthy. Leave the container running so its UDP listener can receive packets. The first connection attempt wakes the game. Connect again once the game server is running.

## Update the image

Read the release notes, put the game server to sleep and [back up your saves outside the Docker host](BACKUP-RESTORE.md). Change the image tag in the existing stack and recreate the container with the same stack name and volume. Then check the state with `nosctl status`.

## Second server instance

Choose a separate stack name so the second instance gets its own data volume. In the `no-one-survived` service, replace the container name and UDP ports. Update the two port variables in the existing `environment:` block.

```yaml
container_name: no-one-survived-2
ports:
  - "7778:7778/udp"
  - "27016:27016/udp"
environment:
  GAME_PORT: "7778"
  QUERY_PORT: "27016"
```
