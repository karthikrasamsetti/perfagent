"""A tiny mock target to develop and (later) run load against — safely.

It intentionally uses only the stdlib so it needs no extra dependencies in Phase 1.
Run it with:  python -m perfagent.sample_target.app   (serves on http://127.0.0.1:8000)

Endpoints:
    GET  /products          -> list of products
    POST /login             -> {"token": ...}
    POST /cart              -> {"ok": true}
    POST /checkout          -> {"order_id": ...}
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_PRODUCTS = [{"id": i, "name": f"item-{i}", "price": 9.99 + i} for i in range(1, 6)]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict | list) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path == "/products":
            self._send(200, _PRODUCTS)
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        routes = {
            "/login": {"token": "demo-token"},
            "/cart": {"ok": True},
            "/checkout": {"order_id": 1001},
        }
        if self.path in routes:
            self._send(200, routes[self.path])
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, *args) -> None:  # keep the test output quiet
        pass


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"mock target listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    serve()
