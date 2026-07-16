from __future__ import annotations

import socket
import threading
import time
import unittest
from unittest.mock import patch

from nos_server.wake import WakeListener


def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class WakeListenerTests(unittest.TestCase):
    def test_private_policy_allows_loopback(self) -> None:
        listener = WakeListener("127.0.0.1", [], source_policy="private")
        self.assertTrue(listener._allowed("127.0.0.1"))
        self.assertTrue(listener._allowed("192.168.10.5"))
        self.assertTrue(listener._allowed("100.64.10.5"))
        self.assertFalse(listener._allowed("198.51.100.5"))

    def test_private_policy_accepts_additional_networks(self) -> None:
        listener = WakeListener(
            "127.0.0.1",
            [],
            source_policy="private",
            allowed_networks=("198.51.100.0/24",),
        )
        self.assertTrue(listener._allowed("198.51.100.5"))

    def test_any_policy_allows_public_source(self) -> None:
        listener = WakeListener("127.0.0.1", [], source_policy="any")
        self.assertTrue(listener._allowed("198.51.100.5"))

    def test_allowlist_policy_denies_unlisted_source(self) -> None:
        listener = WakeListener(
            "127.0.0.1",
            [],
            source_policy="allowlist",
            allowed_networks=("192.0.2.0/24",),
        )
        self.assertTrue(listener._allowed("192.0.2.5"))
        self.assertFalse(listener._allowed("127.0.0.1"))

    def test_wakes_after_configured_packet_count(self) -> None:
        port = free_udp_port()
        listener = WakeListener(
            "127.0.0.1",
            [port],
            source_policy="allowlist",
            allowed_networks=("127.0.0.0/8",),
            packet_count=2,
            packet_window_seconds=5,
            ignore_empty_packets=True,
        )
        self.addCleanup(listener.close)
        stop = threading.Event()
        result: list[object] = []

        thread = threading.Thread(
            target=lambda: result.append(listener.wait(stop, timeout=3))
        )
        thread.start()
        time.sleep(0.1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(b"first", ("127.0.0.1", port))
            time.sleep(0.05)
            client.sendto(b"second", ("127.0.0.1", port))
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(result), 1)
        event = result[0]
        self.assertIsNotNone(event)
        self.assertEqual(event.local_port, port)  # type: ignore[union-attr]
        self.assertEqual(listener._sockets, [])

    def test_socket_stays_bound_across_wait_timeouts(self) -> None:
        port = free_udp_port()
        listener = WakeListener(
            "127.0.0.1",
            [port],
            source_policy="allowlist",
            allowed_networks=("127.0.0.0/8",),
            packet_count=2,
            packet_window_seconds=10,
        )
        self.addCleanup(listener.close)
        stop = threading.Event()
        first: list[object] = []
        thread = threading.Thread(
            target=lambda: first.append(listener.wait(stop, timeout=0.3))
        )
        thread.start()
        time.sleep(0.05)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(b"first", ("127.0.0.1", port))
        thread.join(2)
        self.assertEqual(first, [None])
        self.assertEqual(len(listener._sockets), 1)
        first_socket = listener._sockets[0]

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as competing:
            with self.assertRaises(OSError):
                competing.bind(("127.0.0.1", port))

        second: list[object] = []
        thread = threading.Thread(
            target=lambda: second.append(listener.wait(stop, timeout=1.0))
        )
        thread.start()
        time.sleep(0.05)
        self.assertIs(listener._sockets[0], first_socket)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(b"second", ("127.0.0.1", port))
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertIsNotNone(second[0])
        self.assertEqual(listener._sockets, [])

    def test_packet_history_prunes_expired_sources(self) -> None:
        listener = WakeListener(
            "127.0.0.1", [], packet_count=2, packet_window_seconds=5
        )
        listener._record_packet("192.0.2.1", 1.0)
        listener._record_packet("192.0.2.2", 7.0)
        self.assertNotIn("192.0.2.1", listener._history)
        self.assertIn("192.0.2.2", listener._history)

    def test_packet_history_has_a_source_limit(self) -> None:
        listener = WakeListener(
            "127.0.0.1", [], packet_count=2, packet_window_seconds=60
        )
        with patch("nos_server.wake.MAX_TRACKED_SOURCES", 2):
            listener._record_packet("192.0.2.1", 1.0)
            listener._record_packet("192.0.2.2", 1.0)
            listener._record_packet("192.0.2.3", 1.0)
        self.assertEqual(len(listener._history), 2)
        self.assertNotIn("192.0.2.1", listener._history)

    def test_denies_source_outside_allowlist(self) -> None:
        port = free_udp_port()
        listener = WakeListener(
            "127.0.0.1",
            [port],
            source_policy="allowlist",
            allowed_networks=("192.0.2.0/24",),
        )
        self.addCleanup(listener.close)
        stop = threading.Event()
        thread = threading.Thread(target=lambda: listener.wait(stop, timeout=0.5))
        thread.start()
        time.sleep(0.1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(b"ignored", ("127.0.0.1", port))
        thread.join(2)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
