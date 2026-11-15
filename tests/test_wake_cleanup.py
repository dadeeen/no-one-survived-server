from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from nos_server.wake import WakeListener


class WakeCleanupTests(unittest.TestCase):
    def test_closes_all_created_sockets_when_setup_fails(self) -> None:
        for failed_index in (0, 1):
            for method in ("setsockopt", "bind", "setblocking"):
                with self.subTest(failed_index=failed_index, method=method):
                    sockets = [Mock(), Mock()]
                    getattr(sockets[failed_index], method).side_effect = OSError(
                        "socket setup failed"
                    )
                    selector = Mock()
                    listener = WakeListener("127.0.0.1", [17777, 37015])
                    with (
                        patch("nos_server.wake.socket.socket", side_effect=sockets),
                        patch(
                            "nos_server.wake.selectors.DefaultSelector",
                            return_value=selector,
                        ),
                    ):
                        with self.assertRaisesRegex(OSError, "socket setup failed"):
                            listener.open()
                    for sock in sockets[: failed_index + 1]:
                        sock.close.assert_called_once_with()
                    selector.close.assert_called_once_with()
                    self.assertEqual(listener._sockets, [])
                    self.assertIsNone(listener._selector)


if __name__ == "__main__":
    unittest.main()
