# Portainer deployment

[Deutsch](PORTAINER.de.md) · [Back to README](../README.md)

## Quick start

1. Create the two non-empty password files as described in the [example guide](../examples/README.md#1-create-password-files).
2. Open **Stacks → Add stack → Web editor**.
3. Paste [`examples/portainer-stack.yaml`](../examples/portainer-stack.yaml).
4. Import [`examples/portainer-stack.env.example`](../examples/portainer-stack.env.example) under **Environment variables**.
5. Choose a unique, permanent stack name and deploy.
6. Follow the first installation with `docker logs -f no-one-survived`.

The first deployment downloads the Windows dedicated server and initializes Wine. When `nosctl status` reports `SLEEPING`, setup is complete. The first connection packet only wakes the server; retry after startup.

## Simple and full examples

The recommended pair is intentionally short and covers a normal installation:

- [`examples/portainer-stack.yaml`](../examples/portainer-stack.yaml)
- [`examples/portainer-stack.env.example`](../examples/portainer-stack.env.example)

Advanced deployments can expose every supported setting with:

- [`examples/portainer-stack.full.yaml`](../examples/portainer-stack.full.yaml)
- [`examples/portainer-stack.full.env.example`](../examples/portainer-stack.full.env.example)

Both variants use the same image, persistent data layout, password-file mounts, stop grace period, security option and log rotation. The full files are a reference, not a requirement for normal use.

The root `compose.yaml` uses a local `.env` file and is intended for Docker Compose. For Portainer's web editor, use the dedicated examples above instead of copying the root file.

## GHCR registry access

Public GHCR packages can be pulled without credentials. For a private package, add `ghcr.io` as a Portainer registry using a GitHub personal access token with `read:packages`; use the GitHub username as the registry username.

Image name:

```text
ghcr.io/dadeeen/no-one-survived-server:latest
```

Prefer a tested release tag such as `v0.1.0` for stable operation.

## Why the stack contains comments

Comments are limited to behavior that is not obvious from the setting name:

- the effective project/stack name determines the persistent volume name;
- the 180-second stop grace period lets the supervisor complete Wine shutdown;
- the container remains running in `SLEEPING` so the UDP wake listener stays available;
- password files are mounted read-only outside the stack definition.

Routine variable names are left self-explanatory. Detailed descriptions remain in [Configuration](CONFIGURATION.md).

## Project-scoped data volume

The supplied stacks use the logical volume name `data`:

```yaml
name: ${STACK_NAME:-no-one-survived}

services:
  no-one-survived:
    volumes:
      - data:/data

volumes:
  data:
```

Compose prefixes it with the **effective project name**. With the default project/stack name, the Docker volume normally appears as `no-one-survived_data`.

Portainer's stack name, `docker compose -p`, and `COMPOSE_PROJECT_NAME` can determine or override the effective project name. Do not rename the stack/project after the first deployment. A new name creates a new empty volume; the previous volume remains intact but is no longer mounted automatically.

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
3. Select the tested release tag in the stack variables.
4. Recreate the container without deleting the volume.
5. Verify the server state with `nosctl status`.

When Wine changes and `RESET_WINEPREFIX_ON_VERSION_CHANGE=true`, the prefix is recreated automatically. Saves and game configuration remain in `/data/saved`.
