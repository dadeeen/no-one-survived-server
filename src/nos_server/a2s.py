from __future__ import annotations

import socket
import struct
from dataclasses import dataclass

A2S_INFO_REQUEST = b"\xff\xff\xff\xffTSource Engine Query\x00"
SINGLE_PACKET = b"\xff\xff\xff\xff"
SPLIT_PACKET = b"\xfe\xff\xff\xff"


class A2SError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ServerInfo:
    protocol: int
    name: str
    map_name: str
    folder: str
    game: str
    app_id: int
    players: int
    max_players: int
    bots: int


def _cstring(data: bytes, offset: int) -> tuple[str, int]:
    end = data.find(b"\x00", offset)
    if end < 0:
        raise A2SError("Malformed A2S response: missing string terminator")
    return data[offset:end].decode("utf-8", errors="replace"), end + 1


def parse_info_response(packet: bytes) -> ServerInfo:
    if packet.startswith(SPLIT_PACKET):
        raise A2SError("Split A2S responses are not supported")
    if not packet.startswith(SINGLE_PACKET) or len(packet) < 6:
        raise A2SError("Invalid A2S response header")
    payload = packet[4:]
    if payload[0] != 0x49:  # Source A2S_INFO response
        raise A2SError(f"Unexpected A2S response type 0x{payload[0]:02x}")
    offset = 1
    protocol = payload[offset]
    offset += 1
    name, offset = _cstring(payload, offset)
    map_name, offset = _cstring(payload, offset)
    folder, offset = _cstring(payload, offset)
    game, offset = _cstring(payload, offset)
    if len(payload) < offset + 5:
        raise A2SError("Truncated A2S_INFO response")
    app_id = struct.unpack_from("<H", payload, offset)[0]
    offset += 2
    players, max_players, bots = payload[offset : offset + 3]
    return ServerInfo(
        protocol, name, map_name, folder, game, app_id, players, max_players, bots
    )


def query_info(host: str, port: int, timeout: float = 2.0) -> ServerInfo:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.settimeout(timeout)
        except (OverflowError, ValueError) as exc:
            raise A2SError(f"Invalid A2S timeout {timeout!r}: {exc}") from exc
        sock.sendto(A2S_INFO_REQUEST, (host, port))
        packet, _ = sock.recvfrom(65535)
        # Some servers challenge A2S_INFO with 0x41 + four-byte challenge.
        if packet.startswith(SINGLE_PACKET + b"A") and len(packet) >= 9:
            challenge = packet[5:9]
            sock.sendto(A2S_INFO_REQUEST + challenge, (host, port))
            packet, _ = sock.recvfrom(65535)
        return parse_info_response(packet)
