"""Worker-side loopback HTTP endpoint for k6, backed by the private Unix socket."""

from __future__ import annotations

import socket
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from perfagent.runner.worker_bridge import BridgeError, worker_request
from perfagent.runner.worker_protocol import HOP_HEADERS, MAX_HTTP_BODY_BYTES


class _WorkerHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        # Request paths and response bodies may contain customer data.
        pass

    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def _forward(self):
        if (
            not self.path.startswith("/")
            or self.path.startswith("//")
            or not self.raw_requestline.split()[1].startswith(b"/")
            or self.raw_requestline.split()[1].startswith(b"//")
        ):
            self.send_error(400, "An origin-relative path is required")
            return
        lengths = self.headers.get_all("Content-Length") or []
        if (
            self.headers.get("Transfer-Encoding") is not None
            or len(lengths) > 1
            or (
                lengths
                and (not lengths[0].isascii() or not lengths[0].isdecimal() or len(lengths[0]) > 8)
            )
        ):
            self.send_error(400, "Unsupported request framing")
            return
        length = int(lengths[0]) if lengths else 0
        if length > MAX_HTTP_BODY_BYTES:
            self.send_error(413)
            return
        nominated = _connection_tokens(self.headers.get_all("Connection") or [])
        forwarded = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in HOP_HEADERS | nominated
        }
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                self.send_error(400, "Incomplete request body")
                return
            result = worker_request(
                self.server.bridge,
                self.command,
                self.path,
                forwarded,
                body,
                timeout=self.server.request_timeout,
            )
        except BridgeError:
            self.send_error(502, "The worker broker did not complete the request")
            return
        nominated = _connection_tokens(
            [value for name, value in result.headers if name.lower() == "connection"]
        )
        self.send_response_only(result.status)
        for name, value in result.headers:
            if (
                name.lower() not in HOP_HEADERS | nominated
                and "\r" not in value
                and "\n" not in value
            ):
                self.send_header(name, value)
        if result.status not in (204, 304):
            self.send_header("Content-Length", str(len(result.body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD" and result.status not in (204, 304):
            self.wfile.write(result.body)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = _forward


def _connection_tokens(values: list[str]) -> set[str]:
    return {token.strip().lower() for value in values for token in value.split(",")}


class _WorkerHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, path: Path, max_clients: int, request_timeout: float):
        self.bridge = path
        self.request_timeout = request_timeout
        self.slots = threading.BoundedSemaphore(max_clients)
        super().__init__(("127.0.0.1", 0), _WorkerHTTPHandler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request: socket.socket, client_address) -> None:
        # Clients can disappear during a stop. Avoid dumping request context.
        pass


@contextmanager
def worker_http(path: Path, *, max_clients: int, request_timeout: float):
    """Expose loopback only inside the caller's network namespace."""
    if max_clients < 1 or request_timeout <= 0:
        raise ValueError("Positive HTTP adapter limits are required.")
    with _WorkerHTTPServer(path, max_clients, request_timeout) as server:
        thread = threading.Thread(
            target=server.serve_forever,
            kwargs={"poll_interval": 0.05},
            daemon=True,
        )
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join()
