# Portainer deployment

[Deutsch](PORTAINER.de.md) · [Back to README](../README.md) · [Configuration reference](CONFIGURATION.md)

## Quick start

1. Create the two non-empty password files as described in the [example guide](../examples/README.md#1-create-password-files).
2. Open **Stacks → Add stack → Web editor**.
3. Paste [`examples/portainer-stack.yaml`](../examples/portainer-stack.yaml).
4. Edit the visible values directly in the YAML.
5. Choose a unique, permanent stack name and deploy.
6. Follow the first installation with `docker logs -f no-one-survived`.

No separate environment file is required. The stack contains the common settings for a normal installation. Add optional variables from the [configuration reference](CONFIGURATION.md) only when needed.

The first deployment downloads the Windows dedicated server and initializes Wine. When `nosctl status` reports `SLEEPING`, setup is complete. The first connection packet only wakes the server; retry after startup.

## GHCR registry access

Public GHCR packages can be pulled without credentials. For a private package, add `ghcr.io` as a Portainer registry using a GitHub personal access token with `read:packages`; use the GitHub username as the registry username.

Image name:

```text
ghcr.io/dadeeen/no-one-survived-server:latest
```

For stable operation, replace `latest` in the stack with a tested release tag such as `v0.1.0`.

## Editing the stack

The example intentionally uses direct values instead of `${VARIABLE}` placeholders. Edit common settings in place:

```yaml
environment:
  TZ: Europe/Berlin
  SERVER_NAME: My NoS Server
  MAX_PLAYERS: "8"
  IDLE_TIMEOUT_SECONDS: "3600"
```

Optional settings can be added to the same `environment:` block. Keep boolean and numeric values quoted in YAML to make their string representation explicit.

The comments are limited to behavior that is not obvious from a setting name:

- the Portainer stack name determines the persistent volume name;
- the 180-second stop grace period lets the supervisor complete Wine shutdown;
- the container remains running in `SLEEPING` so the UDP wake listener stays available;
- password files are mounted read-only outside the stack definition.

## Project-scoped data volume

The supplied stack uses the logical volume name `data`:

```yaml
services:
  no-one-survived:
    volumes:
      - data:/data

volumes:
  data:
```

Portainer prefixes it with the stack name. A stack named `no-one-survived` normally creates the Docker volume `no-one-survived_data`.

Do not rename the stack after the first deployment. A new name creates a new empty volume; the previous volume remains intact but is no longer mounted automatically.

For a second instance, use a different permanent stack name, container name and host ports. Its volume is isolated automatically.

## Operating from Portainer

Stopping the container disables automatic wake because no listener remains. Usually leave the container running in `SLEEPING` and let only the game process sleep.

```bash
docker exec no-one-survived nosctl status
```

Portainer reports the container as healthy while sleeping. This is intentional.

## Updating the image

1. Read the release notes and base-image change.
2. Back up `/data/saved` outside the container host.
3. Replace the tag in the stack's `image:` line with the tested release tag.
4. Recreate the container without deleting the volume.
5. Verify the server state with `nosctl status`.

When Wine changes and `RESET_WINEPREFIX_ON_VERSION_CHANGE=true`, the prefix is recreated automatically. Saves and game configuration remain in `/data/saved`.
