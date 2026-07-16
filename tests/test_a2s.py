from __future__ import annotations

import struct
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


class A2STests(unittest.TestCase):
    def test_parses_player_count(self) -> None:
        info = parse_info_response(fixture())
        self.assertEqual(info.name, "Test Server")
        self.assertEqual(info.map_name, "Map01")
        self.assertEqual(info.players, 3)
        self.assertEqual(info.max_players, 8)

    def test_rejects_invalid_header(self) -> None:
        with self.assertRaises(A2SError):
            parse_info_response(b"bad")

    def test_normalizes_platform_timeout_overflow(self) -> None:
        with self.assertRaisesRegex(A2SError, "Invalid A2S timeout"):
            query_info("127.0.0.1", 27015, 1e300)


if __name__ == "__main__":
    unittest.main()
