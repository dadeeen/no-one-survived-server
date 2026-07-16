# Networking and wake security

[Deutsch](NETWORKING.de.md) · [Back to README](../README.md)

The container is network-neutral. It can be used in a LAN, through a routed VPN, or on publicly reachable UDP ports. The network topology only changes routing, firewall rules and which sources may wake a sleeping server.

## Required ports

| Purpose | Protocol | Default |
|---|---|---:|
| Game traffic and wake | UDP | 7777 |
| Steam query, player count and wake | UDP | 27015 |

Publish the same host and container port numbers:

```yaml
ports:
  - "7777:7777/udp"
  - "27015:27015/udp"
```

Allow both UDP ports in the host, LXC/VM and upstream firewall from the networks that should connect. This project does not require a TCP port.

## Simple and safe default

The default is:

```env
WAKE_SOURCE_POLICY=private
WAKE_ALLOWED_NETWORKS=
```

`private` accepts wake packets from these IPv4 ranges:

- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.0.0/16`
- `100.64.0.0/10` for overlay/CGNAT-style addressing such as Tailscale
- `127.0.0.0/8` for local tests

This covers most home LANs, Docker bridge networks, site-to-site VPNs and overlay VPNs without requiring users to know their CIDR ranges. Public IPv4 sources are denied by default.

## Wake source policies

| Policy | Behavior | Typical use |
|---|---|---|
| `private` | Built-in private ranges plus optional `WAKE_ALLOWED_NETWORKS` | Recommended default for LAN/VPN use |
| `allowlist` | Only explicitly listed CIDRs; an empty list is rejected | Strict installations or unusual routed networks |
| `any` | Every IPv4 source that can reach the UDP port may wake the server | Deliberately public servers |

### Add an extra routed network

With `private`, `WAKE_ALLOWED_NETWORKS` adds networks to the built-in ranges:

```env
WAKE_SOURCE_POLICY=private
WAKE_ALLOWED_NETWORKS=198.51.100.0/24
```

The documentation range above is only an example. Enter the source subnet actually seen by the container.

### Strict allowlist

```env
WAKE_SOURCE_POLICY=allowlist
WAKE_ALLOWED_NETWORKS=192.168.10.0/24,10.50.0.0/24
```

In this mode, loopback and private networks are not implicitly trusted. Every permitted source network must be listed.

### Public wake

```env
WAKE_SOURCE_POLICY=any
WAKE_PACKET_COUNT=2
```

Use this only when public wake is intentional. Internet scanners, monitoring systems and Steam queries may otherwise start the server. Raising `WAKE_PACKET_COUNT` reduces accidental wakes but is not an access-control mechanism.

## LAN

Connect to the LAN address of the Docker host, VM or LXC, for example:

```text
192.168.10.50:7777
```

The default `private` policy accepts the wake packet. The first packet only starts the server, so reconnect after the state changes to `RUNNING` or `IDLE`:

```bash
docker exec no-one-survived nosctl status
```

## Routed VPNs: WireGuard, Tailscale and similar

A routed VPN can reach the same private server address. Requirements:

- client and server networks do not overlap;
- a route exists to the server subnet and back to the client subnet;
- firewalls permit UDP 7777 and 27015;
- the source address seen by the container is allowed by the selected wake policy.

RFC1918 remote LANs and Tailscale's `100.64.0.0/10` range work with the default `private` policy. Add a custom non-private tunnel range through `WAKE_ALLOWED_NETWORKS` when needed.

Use direct IP or a Steam favorite. Layer-2 broadcast discovery is normally not forwarded through a routed VPN.

## Public IPv4

A normal public IPv4 deployment needs router/NAT forwarding and firewall rules for both UDP ports. To allow arbitrary internet clients to wake the server, explicitly select:

```env
WAKE_SOURCE_POLICY=any
```

A stricter alternative is `allowlist`, but it is inconvenient for players with changing public addresses.

## DS-Lite and CGNAT

DS-Lite and CGNAT normally prevent unsolicited inbound public IPv4 port forwarding. They do not affect:

- clients in the same LAN;
- traffic through an already established site-to-site VPN;
- outbound-established overlay networks such as Tailscale;
- a VPN or relay hosted on a publicly reachable VPS.

This image does not provide a relay or bypass DS-Lite. The current wake listener and source filtering are IPv4-only; native public IPv6 wake is not promised by this release.

## Wake policy is not a firewall

`WAKE_SOURCE_POLICY` controls only whether a packet may start a sleeping game process. It does **not** decide who can join after the server is running.

Actual access is controlled by:

- router and firewall rules;
- Docker port bindings;
- VPN routing and ACLs;
- the game server password.

A source denied by the wake policy may still connect later if another user started the server and the network/firewall allows it.

## Verify the observed source address

After a wake test, inspect the logs:

```text
[wake] Accepted wake packet from 192.168.20.25:54321 -> UDP/27015
```

If NAT or a proxy rewrites the source, permit the translated subnet rather than the original client subnet.

## Troubleshooting commands

```bash
ss -lunp | grep -E ':(7777|27015)\b'
docker port no-one-survived
docker logs --tail 200 no-one-survived
```

Expected port ownership:

- `SLEEPING`: the Python wake listener owns the selected ports;
- `RUNNING` or `IDLE`: Wine/WRSH owns the ports.
