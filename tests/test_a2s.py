from __future__ import annotations

import struct
import socket
import threading
import unittest

from nos_server.a2s import A2SError, parse_info_response, query_info


def fixture(players: int = 3, maximum: int = 8) -> bytes:
    payload = bytearray(b"\xff\xff\xff\xffI")
    payload.append(17)
    for value in ("Test Server", "Map01", "WRSH", "No One Survived"):
        payload.extend(value.encode())
        payload.append(0)
    payload.extend(struct.pack("<H", 1963370 & 0xFFFF))
    payload.extend(bytes([players, maximum, 0]))
    payload.extend(b"dwl")
    return bytes(payload)


def fixture_with_game_id(app_id: int) -> bytes:
    payload = bytearray(b"\xff\xff\xff\xffI")
    payload.append(17)
    for value in ("Test Server", "Map01", "WRSH", "No One Survived"):
        payload.extend(value.encode())
        payload.append(0)
    payload.extend(struct.pack("<H", app_id & 0xFFFF))
    payload.extend(bytes([3, 8, 0]))
    payload.extend(b"dl")
    payload.extend(bytes([0, 1]))
    payload.extend(b"1.0\x00")
    payload.append(0x01)
    payload.extend(struct.pack("<Q", app_id))
    return bytes(payload)


class A2STests(unittest.TestCase):
    def test_challenge_and_reply_ignore_packets_from_other_endpoints(self) -> None:
        with (
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server,
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as unrelated,
        ):
            server.bind(("127.0.0.1", 0))
            server.settimeout(2)
            received = []
            failures = []

            def respond():
                try:
                    request, client = server.recvfrom(65535)
                    received.append(request)
                    unrelated.sendto(fixture(players=0), client)
                    server.sendto(b"\xff\xff\xff\xffAabcd", client)
                    request, client = server.recvfrom(65535)
                    received.append(request)
                    unrelated.sendto(fixture(players=0), client)
                    server.sendto(fixture(players=3), client)
                except Exception as exc:
                    failures.append(exc)

            thread = threading.Thread(target=respond)
            thread.start()
            try:
                info = query_info("127.0.0.1", server.getsockname()[1])
            finally:
                thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(info.players, 3)
            self.assertEqual(received[1], received[0] + b"abcd")

    def test_parses_player_count(self) -> None:
        info = parse_info_response(fixture())
        self.assertEqual(info.name, "Test Server")
        self.assertEqual(info.map_name, "Map01")
        self.assertEqual(info.players, 3)
        self.assertEqual(info.max_players, 8)

    def test_prefers_full_app_id_from_extended_game_id(self) -> None:
        info = parse_info_response(fixture_with_game_id(2329680))
        self.assertEqual(info.app_id, 2329680)
        self.assertEqual(info.game_id, 2329680)

    def test_rejects_invalid_header(self) -> None:
        with self.assertRaises(A2SError):
            parse_info_response(b"bad")

    def test_normalizes_platform_timeout_overflow(self) -> None:
        with self.assertRaisesRegex(A2SError, "Invalid A2S timeout"):
            query_info("127.0.0.1", 27015, 1e300)


if __name__ == "__main__":
    unittest.main()
