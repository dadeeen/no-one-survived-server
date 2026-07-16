# Troubleshooting

[Deutsch](TROUBLESHOOTING.de.md) · [Back to README](../README.md)

## Container is healthy but the server is not visible

Run:

```bash
docker exec no-one-survived nosctl status
```

`SLEEPING` is healthy by design. Trigger a query/direct connection or run `nosctl wake`. Wait for `RUNNING`/`IDLE`, then retry the client connection.

## A packet does not wake the server

Check:

- UDP, not TCP, is published;
- `WAKE_ON_GAME_PORT` or `WAKE_ON_QUERY_PORT` is true;
- source address is accepted by `WAKE_SOURCE_POLICY`;
- with `allowlist`, `WAKE_ALLOWED_NETWORKS` contains the observed source subnet;
- `WAKE_PACKET_COUNT` is not higher than the number of attempts;
- firewall rules permit the packet;
- the container, rather than only the game process, is running.

Logs show accepted packets. Denied packets are intentionally not logged to avoid log flooding.

## The server wakes immediately after sleeping

Increase:

```env
WAKE_ARM_DELAY_SECONDS=15
WAKE_PACKET_COUNT=2
```

Keep `WAKE_SOURCE_POLICY=private` or use a strict `allowlist`. Repeated Steam favorite refreshes or monitoring systems can generate query packets.

## Automatic sleep never occurs

Inspect `nosctl status` for:

- `players`;
- `a2s_ok`;
- `a2s_error`;
- `state` and `state_since`.

The default fail-safe does not sleep after A2S failures. Verify the query port, server response and identical host/container port numbers. `ALLOW_LOG_ONLY_IDLE=true` is available, but may be unsafe if log formats change.

## SteamCMD update fails

The first installation requires internet access and enough free space. Review the complete SteamCMD output. For an existing installation only, `START_ON_UPDATE_FAILURE=true` permits startup with old files. Do not use it to mask a permanently broken initial install.

Repair mode:

```env
VALIDATE_ON_UPDATE=true
```

Return it to false after a successful validation.

## Wine prefix problems after an image update

Set once:

```env
RESET_WINEPREFIX=true
```

Recreate the container, then remove the variable. `/data/saved` is separate and is not deleted.

## Permission errors

Check the volume owner and configured IDs:

```bash
docker exec no-one-survived id
docker exec no-one-survived ls -ld /data /data/saved
```

Change `PUID`/`PGID` or remove the matching `/data/.ownership-*` marker and recreate the container so ownership is reapplied.

## Server process repeatedly crashes

After `MAX_CRASH_RESTARTS`, the supervisor enters `ERROR` and the health check fails. Collect:

```bash
docker logs no-one-survived > nos-container.log
docker exec no-one-survived find /data/saved/Logs -maxdepth 1 -type f -printf '%f\n'
```

Check game updates, Wine changes, invalid `Game.ini` values and free memory. Do not simply raise the restart limit indefinitely.

## First installation replaced or moved a Saved directory

If SteamCMD created a real server-side `Saved` directory while `/data/saved` already contained data, the supervisor moves the conflicting directory to:

```text
/data/state/orphaned-server-saved-<timestamp>
```

This avoids silent data loss. Compare it manually before deletion.
