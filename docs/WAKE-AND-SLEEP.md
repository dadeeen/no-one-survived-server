# Wake-on-packet and automatic sleep

[Deutsch](WAKE-AND-SLEEP.de.md) · [Back to README](../README.md)

## State model

```text
PREPARING -> SLEEPING -> STARTING -> RUNNING -> IDLE -> STOPPING -> SLEEPING
                  ^          |          |          |
                  |          +-- crash -+          +-- timeout
                  +------------- UDP/manual wake
```

The container remains alive in `SLEEPING`; only the Wine/game process is stopped. This avoids Docker socket access and lets the same container bind the published UDP ports as a wake listener.

## Packet handover

1. The listener binds the selected UDP ports.
2. It ignores empty packets and sources rejected by `WAKE_SOURCE_POLICY`.
3. It counts packets per source IP inside `WAKE_PACKET_WINDOW_SECONDS`.
4. After `WAKE_PACKET_COUNT`, it closes all listener sockets.
5. The supervisor starts Wine and `WRSHServer.exe`, which then bind the same ports.

UDP has no connection state to preserve. The wake packet cannot be handed to a process that was not yet running, so the first join/query attempt is expected to time out. Retry after startup.

## Choosing the wake threshold

`WAKE_PACKET_COUNT=1` gives the fastest experience and normally works well behind LAN/VPN firewalls. Use `2` or `3` when the ports are exposed to untrusted networks and random scanning causes starts.

The count is maintained per source IP, not globally. An attacker from one IP cannot combine packets with another source to reach the threshold.

## Wake source policy

The recommended default is intentionally simple:

```env
WAKE_SOURCE_POLICY=private
WAKE_ALLOWED_NETWORKS=
```

`private` trusts common LAN, Docker and overlay IPv4 ranges and denies public IPv4 sources. Optional `WAKE_ALLOWED_NETWORKS` entries extend those built-in ranges.

For a strict list, use:

```env
WAKE_SOURCE_POLICY=allowlist
WAKE_ALLOWED_NETWORKS=192.168.10.0/24,10.50.0.0/24
```

For deliberately public wake, use `WAKE_SOURCE_POLICY=any` and consider increasing `WAKE_PACKET_COUNT`. The wake policy is not a firewall: it only controls whether the sleeping process starts.

The source address is evaluated as seen inside the container. With normal Docker port publishing, the original LAN source is usually preserved for UDP. Verify it in the wake log; if NAT or a proxy rewrites it, allow the translated subnet.

## Idle decision

The supervisor sends an A2S_INFO request to the local Steam query port. It starts an idle timer only after a successful response reporting zero players. Any of the following cancels the timer:

- one or more players;
- an A2S timeout or malformed response;
- a server process exit;
- manual shutdown.

Before sleeping, the supervisor requires:

- `MIN_UPTIME_SECONDS` elapsed;
- `IDLE_TIMEOUT_SECONDS` continuous zero-player time;
- at least `IDLE_MIN_SUCCESSFUL_QUERIES` consecutive successful zero-player responses.

This fail-safe policy favors leaving a server running over disconnecting players.

## Manual operation

```bash
docker exec no-one-survived nosctl wake
docker exec no-one-survived nosctl sleep
```

`nosctl sleep` is an administrative forced sleep request. It does not block when players are online. Check `nosctl status` first.

## Update interaction

Recommended:

```env
UPDATE_ON_CONTAINER_START=true
UPDATE_ON_WAKE=false
UPDATE_INTERVAL_SECONDS=0
```

This prepares a current server once when the container starts and keeps later wake latency low. A nonzero update interval runs SteamCMD while sleeping. `UPDATE_ON_WAKE=true` is safest for version matching but can turn each wake into a long update.
