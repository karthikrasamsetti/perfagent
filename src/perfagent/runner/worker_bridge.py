"""Private per-run Unix transport for the managed HTTPS broker."""

from __future__ import annotations

import base64
import binascii
import http.client
import json
import socket
import socketserver
import struct
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from perfagent.runner.worker_protocol import BrokerResponse, EgressDenied

if TYPE_CHECKING:
    from perfagent.runner.managed_egress import ManagedEgress

_MAX_FRAME = 3 * 1024 * 1024
_REQUEST_FIELDS = {"method", "path", "headers", "body"}


class BridgeError(RuntimeError):
    """The broker rejected a request or the worker connection failed."""


def _read_exact(conn: socket.socket, size: int, deadline: float) -> bytes:
    data = bytearray()
    while len(data) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Worker frame deadline exceeded.")
        conn.settimeout(remaining)
        chunk = conn.recv(min(size - len(data), 65536))
        if not chunk:
            raise EOFError("Incomplete worker frame.")
        data.extend(chunk)
    return bytes(data)


def _recv(conn: socket.socket, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    (size,) = struct.unpack("!I", _read_exact(conn, 4, deadline))
    if not 0 < size <= _MAX_FRAME:
        raise ValueError("Invalid worker frame size.")
    message = json.loads(_read_exact(conn, size, deadline))
    if not isinstance(message, dict):
        raise ValueError("Invalid worker message.")
    return message


def _send(conn: socket.socket, message: dict, timeout: float) -> None:
    data = json.dumps(message, separators=(",", ":")).encode()
    if len(data) > _MAX_FRAME:
        raise ValueError("Worker frame exceeds its size limit.")
    conn.settimeout(timeout)
    conn.sendall(struct.pack("!I", len(data)) + data)


def _dispatch(broker: ManagedEgress, message: dict) -> dict:
    if set(message) != _REQUEST_FIELDS:
        raise ValueError("Invalid worker request fields.")
    method, path, headers, encoded = (
        message["method"],
        message["path"],
        message["headers"],
        message["body"],
    )
    if (
        not isinstance(method, str)
        or not isinstance(path, str)
        or not isinstance(encoded, str)
        or not isinstance(headers, dict)
        or not all(isinstance(value, str) for value in headers.values())
    ):
        raise ValueError("Invalid worker request types.")
    result = broker.request(method, path, headers, base64.b64decode(encoded, validate=True))
    return {
        "status": result.status,
        "headers": result.headers,
        "body": base64.b64encode(result.body).decode("ascii"),
    }


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        try:
            response = _dispatch(self.server.broker, _recv(self.request, timeout=2))
        except EgressDenied as error:
            response = {"error": str(error)}
        except (ValueError, binascii.Error, EOFError, RecursionError):
            response = {"error": "Invalid worker request."}
        except (OSError, http.client.HTTPException):
            response = {"error": "The approved destination request failed."}
        try:
            _send(self.request, response, timeout=2)
        except (OSError, ValueError):
            pass


class _Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

    def __init__(self, path: Path, broker: ManagedEgress, max_clients: int):
        self.broker = broker
        self.slots = threading.BoundedSemaphore(max_clients)
        self._client_lock = threading.Lock()
        self._clients = set()
        super().__init__(str(path), _Handler)
        path.chmod(0o600)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        with self._client_lock:
            self._clients.add(request)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._release(request)
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._release(request)

    def _release(self, request):
        with self._client_lock:
            self._clients.discard(request)
        self.slots.release()

    def interrupt_clients(self):
        with self._client_lock:
            for conn in self._clients:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass


@contextmanager
def worker_bridge(broker: ManagedEgress, *, max_clients: int):
    """Return a private socket path and close its broker when the run ends."""
    if max_clients < 1:
        raise ValueError("At least one worker connection is required.")
    # A short path also fits sockaddr_un on macOS.
    with tempfile.TemporaryDirectory(prefix="pa-worker-", dir="/tmp") as directory:
        path = Path(directory) / "egress.sock"
        with _Server(path, broker, max_clients) as server:
            thread = threading.Thread(
                target=server.serve_forever,
                kwargs={"poll_interval": 0.05},
                daemon=True,
            )
            thread.start()
            try:
                yield path
            finally:
                broker.close()
                server.shutdown()
                server.interrupt_clients()
                thread.join()


def worker_request(
    path: Path,
    method: str,
    target_path: str,
    headers: dict[str, str],
    body: bytes,
    *,
    timeout: float,
) -> BrokerResponse:
    """Send one request from an isolated worker over its mounted socket."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(timeout)
            conn.connect(str(path))
            _send(
                conn,
                {
                    "method": method,
                    "path": target_path,
                    "headers": headers,
                    "body": base64.b64encode(body).decode("ascii"),
                },
                timeout,
            )
            result = _recv(conn, timeout)
    except (OSError, EOFError, ValueError) as error:
        raise BridgeError("The private worker connection failed.") from error
    if "error" in result:
        raise BridgeError(result["error"])
    return BrokerResponse(
        result["status"],
        tuple(map(tuple, result["headers"])),
        base64.b64decode(result["body"], validate=True),
    )
