from __future__ import annotations

import ipaddress
import selectors
import socket
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from threading import Event
from typing import cast


PRIVATE_WAKE_NETWORKS = (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "100.64.0.0/10",
    "127.0.0.0/8",
)
MAX_TRACKED_SOURCES = 4096


@dataclass(frozen=True, slots=True)
class WakeEvent:
    source_ip: str
    source_port: int
    local_port: int
    packet_size: int
    monotonic_time: float


class WakeListener:
    def __init__(
        self,
        bind_address: str,
        ports: list[int],
        source_policy: str = "private",
        allowed_networks: tuple[str, ...] = (),
        packet_count: int = 1,
        packet_window_seconds: int = 5,
        ignore_empty_packets: bool = True,
    ) -> None:
        if source_policy not in {"private", "allowlist", "any"}:
            raise ValueError(f"Unknown wake source policy: {source_policy}")
        if source_policy == "allowlist" and not allowed_networks:
            raise ValueError("allowlist wake policy requires at least one network")
        self.bind_address = bind_address
        self.ports = sorted(set(ports))
        self.source_policy = source_policy
        networks = list(allowed_networks)
        if source_policy == "private":
            networks = [*PRIVATE_WAKE_NETWORKS, *networks]
        self.networks = tuple(
            ipaddress.ip_network(item, strict=False) for item in networks
        )
        self.packet_count = packet_count
        self.packet_window_seconds = packet_window_seconds
        self.ignore_empty_packets = ignore_empty_packets
        self._sockets: list[socket.socket] = []
        self._selector: selectors.BaseSelector | None = None
        self._history: OrderedDict[str, deque[float]] = OrderedDict()

    def _allowed(self, address: str) -> bool:
        if self.source_policy == "any":
            return True
        ip = ipaddress.ip_address(address)
        return any(ip in network for network in self.networks)

    def _ensure_open(self) -> selectors.BaseSelector:
        if self._selector is not None:
            return self._selector
        selector = selectors.DefaultSelector()
        try:
            for port in self.ports:
                listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener_sock.bind((self.bind_address, port))
                listener_sock.setblocking(False)
                self._sockets.append(listener_sock)
                selector.register(listener_sock, selectors.EVENT_READ, data=port)
        except BaseException:
            selector.close()
            for listener_sock in self._sockets:
                listener_sock.close()
            self._sockets.clear()
            raise
        self._selector = selector
        return selector

    def close(self) -> None:
        if self._selector is not None:
            self._selector.close()
            self._selector = None
        for sock in self._sockets:
            try:
                sock.close()
            except OSError:
                pass
        self._sockets.clear()

    def _prune_history(self, now: float) -> None:
        cutoff = now - self.packet_window_seconds
        for source_ip in list(self._history):
            entries = self._history[source_ip]
            while entries and entries[0] < cutoff:
                entries.popleft()
            if not entries:
                del self._history[source_ip]

    def _record_packet(self, source_ip: str, now: float) -> bool:
        self._prune_history(now)
        entries = self._history.get(source_ip)
        if entries is None:
            if len(self._history) >= MAX_TRACKED_SOURCES:
                self._history.popitem(last=False)
            entries = deque()
            self._history[source_ip] = entries
        else:
            self._history.move_to_end(source_ip)
        entries.append(now)
        return len(entries) >= self.packet_count

    def wait(self, stop_event: Event, timeout: float | None = None) -> WakeEvent | None:
        if not self.ports:
            stop_event.wait(timeout)
            return None
        selector = self._ensure_open()
        started = time.monotonic()
        while not stop_event.is_set():
            if timeout is not None:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    return None
                select_timeout = min(0.5, remaining)
            else:
                select_timeout = 0.5
            for key, _ in selector.select(select_timeout):
                ready_sock = cast(socket.socket, key.fileobj)
                try:
                    payload, source = ready_sock.recvfrom(65535)
                except BlockingIOError:
                    continue
                source_ip, source_port = source[0], source[1]
                if self.ignore_empty_packets and not payload:
                    continue
                if not self._allowed(source_ip):
                    continue
                now = time.monotonic()
                if self._record_packet(source_ip, now):
                    event = WakeEvent(
                        source_ip, source_port, int(key.data), len(payload), now
                    )
                    self.close()
                    return event
        self.close()
        return None
