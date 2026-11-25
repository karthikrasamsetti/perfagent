"""Send managed worker requests through one pinned HTTPS destination.

This boundary is intended for a broker outside the worker network namespace. It
does not listen on a network interface or grant the worker direct network access.
"""

from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit

from perfagent.runner.admission import https_origin
from perfagent.runner.worker_protocol import (
    HOP_HEADERS,
    MAX_HTTP_BODY_BYTES,
    BrokerResponse,
    EgressDenied,
)

_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
_HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")


class _PinnedConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: str, timeout: float, context: ssl.SSLContext):
        super().__init__(host, port=port, timeout=timeout, context=context)
        self.address = address
        self.stream: socket.socket | None = None

    def connect(self) -> None:
        family = socket.AF_INET6 if ":" in self.address else socket.AF_INET
        raw = socket.socket(family, socket.SOCK_STREAM)
        self.stream = raw
        raw.settimeout(self.timeout)
        try:
            raw.connect((self.address, self.port))
            self.sock = self._context.wrap_socket(
                raw,
                server_hostname=self.host,
                do_handshake_on_connect=False,
            )
            self.stream = self.sock
            self.sock.do_handshake()
        except BaseException:
            self.stream.close()
            raise


class ManagedEgress:
    """Bound a single run by destination, concurrency, request rate, and deadline."""

    def __init__(
        self, origin: str, address: str, *, max_rps: int, max_active: int, max_seconds: int
    ):
        parsed = urlsplit(origin)
        if (
            not https_origin(origin)
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("An exact HTTPS origin is required.")
        self._host = parsed.hostname
        self._port = parsed.port or 443
        peer = ipaddress.ip_address(address)
        if (
            peer.is_unspecified
            or peer.is_multicast
            or peer.is_link_local
            or getattr(peer, "scope_id", None) is not None
        ):
            raise ValueError("The pinned destination must be an explicit unicast address.")
        if min(max_rps, max_active, max_seconds) < 1:
            raise ValueError("Run limits must be positive.")
        self._address = str(peer)
        self._context = ssl.create_default_context()
        self._deadline = time.monotonic() + max_seconds
        self._interval = 1 / max_rps
        self._next_start = 0.0
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(max_active)
        self._closed = False
        self._connections: set[_PinnedConnection] = set()

    def _admit(self, connection: _PinnedConnection) -> None:
        with self._lock:
            now = time.monotonic()
            if self._closed or now >= self._deadline:
                raise EgressDenied("The run has stopped.")
            if now < self._next_start:
                raise EgressDenied("The request rate limit was reached.")
            self._next_start = now + self._interval
            self._connections.add(connection)

    def close(self) -> None:
        """Deny subsequent requests and interrupt active broker connections."""
        with self._lock:
            self._closed = True
            for connection in self._connections:
                self._interrupt(connection)

    @staticmethod
    def _interrupt(connection: _PinnedConnection) -> None:
        sock = connection.stream
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def request(
        self, method: str, path: str, headers: dict[str, str], body: bytes
    ) -> BrokerResponse:
        if (
            method not in _METHODS
            or not path.startswith("/")
            or path.startswith("//")
            or "\\" in path
            or "#" in path
            or not path.isascii()
            or any(ord(char) <= 32 or ord(char) == 127 for char in path)
        ):
            raise EgressDenied("Only an origin-relative HTTP request is allowed.")
        if len(path) > 8192 or len(body) > MAX_HTTP_BODY_BYTES or len(headers) > 64:
            raise EgressDenied("The request exceeds the broker size limit.")
        clean_headers = {}
        for name, value in headers.items():
            if (
                not _HEADER_NAME.fullmatch(name)
                or name.lower() in HOP_HEADERS
                or len(value) > 8192
                or any(ord(c) < 32 or ord(c) > 126 for c in value)
            ):
                raise EgressDenied("The request contains an unsupported header.")
            clean_headers[name] = value
        if not self._slots.acquire(blocking=False):
            raise EgressDenied("The connection limit was reached.")
        connection = _PinnedConnection(
            self._host,
            self._port,
            self._address,
            max(0.01, self._deadline - time.monotonic()),
            self._context,
        )
        timer = None
        try:
            self._admit(connection)
            timer = threading.Timer(
                max(0, self._deadline - time.monotonic()), self._interrupt, args=(connection,)
            )
            timer.daemon = True
            timer.start()
            connection.connect()
            with self._lock:
                if self._closed or time.monotonic() >= self._deadline:
                    raise EgressDenied("The run has stopped.")
            connection.request(method, path, body=body, headers=clean_headers)
            with connection.getresponse() as response:
                result = response.read(MAX_HTTP_BODY_BYTES + 1)
                if len(result) > MAX_HTTP_BODY_BYTES:
                    raise EgressDenied("The response exceeds the broker size limit.")
                return BrokerResponse(response.status, tuple(response.getheaders()), result)
        finally:
            if timer:
                timer.cancel()
            connection.close()
            with self._lock:
                self._connections.discard(connection)
            self._slots.release()
