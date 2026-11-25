import http.client
import os
import shutil
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from perfagent.runner import managed_egress
from perfagent.runner.docker_worker import docker_worker
from perfagent.runner.k6_binary import find_k6
from perfagent.runner.managed_egress import EgressDenied, ManagedEgress
from perfagent.runner.worker_bridge import BridgeError, worker_bridge, worker_request
from perfagent.runner.worker_job import run_worker_job


def test_egress_pins_peer_checks_tls_and_never_follows_redirects(tmp_path, monkeypatch):
    openssl = shutil.which("openssl")
    if not openssl:
        pytest.skip("OpenSSL is required for the loopback TLS fixture.")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run([
        openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-subj", "/CN=approved.test", "-keyout", str(key), "-out", str(cert),
    ], check=True, capture_output=True)
    observed = []
    blocking = threading.Event()
    release = threading.Event()
    stopped = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            observed.append((self.path, self.headers["Host"]))
            if self.path == "/slow":
                blocking.set()
                release.wait(timeout=3)
                return
            self.send_response(302)
            self.send_header("Location", "https://other.example.test/redirect")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cert, key)
        server.socket = tls.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client_tls = ssl.create_default_context(cafile=str(cert))
        monkeypatch.setattr(managed_egress.ssl, "create_default_context", lambda: client_tls)
        try:
            origin = f"https://approved.test:{server.server_port}"
            broker = ManagedEgress(origin, "127.0.0.1", max_rps=1, max_active=1, max_seconds=10)
            response = broker.request("GET", "/checkout", {}, b"")
            assert response.status == 302
            assert observed == [("/checkout", origin.removeprefix("https://"))]
            with pytest.raises(EgressDenied, match="rate limit"):
                broker.request("GET", "/checkout", {}, b"")
            broker.close()
            with pytest.raises(EgressDenied, match="stopped"):
                broker.request("GET", "/checkout", {}, b"")

            other_name = ManagedEgress(
                f"https://wrong.test:{server.server_port}", "127.0.0.1",
                max_rps=1, max_active=1, max_seconds=10,
            )
            with pytest.raises(ssl.SSLCertVerificationError):
                other_name.request("GET", "/checkout", {}, b"")
            assert len(observed) == 1

            bridged = ManagedEgress(
                origin, "127.0.0.1", max_rps=1, max_active=1, max_seconds=10
            )
            with worker_bridge(bridged, max_clients=2) as socket_path:
                assert socket_path.stat().st_mode & 0o777 == 0o600
                with pytest.raises(BridgeError, match="origin-relative"):
                    worker_request(socket_path, "GET", "https://other.test/", {}, b"", timeout=2)
                result = worker_request(socket_path, "GET", "/checkout", {}, b"", timeout=2)
                assert result.status == 302
                assert observed == [("/checkout", origin.removeprefix("https://"))] * 2
                with pytest.raises(BridgeError, match="rate limit"):
                    worker_request(socket_path, "GET", "/checkout", {}, b"", timeout=2)
            assert not socket_path.exists()
            with pytest.raises(EgressDenied, match="stopped"):
                bridged.request("GET", "/checkout", {}, b"")

            script = tmp_path / "worker.js"
            script.write_text("""import http from 'k6/http';
import { check } from 'k6';
export const options = { iterations: 1, thresholds: { checks: ['rate==1'] } };
export default function () {
  const response = http.get(__ENV.BASE_URL + '/checkout');
  check(response, { 'redirect returned unchanged': r => r.status === 302 });
}
""")
            k6 = find_k6()
            if k6:
                isolated = ManagedEgress(
                    origin, "127.0.0.1", max_rps=1, max_active=1, max_seconds=10,
                )
                with worker_bridge(isolated, max_clients=2) as socket_path:
                    assert run_worker_job(
                        Path(k6).absolute(), script, socket_path, max_seconds=8, max_clients=2,
                    ) == 0
                assert observed == [("/checkout", origin.removeprefix("https://"))] * 3

            worker_image = os.environ.get("PERFAGENT_TEST_WORKER_IMAGE")
            if worker_image:
                prior_count = len(observed)
                docker_broker = ManagedEgress(
                    origin, "127.0.0.1", max_rps=1, max_active=1, max_seconds=20,
                )
                with worker_bridge(docker_broker, max_clients=2) as socket_path:
                    with docker_worker(
                        worker_image, socket_path, script.read_text(), max_seconds=8, max_clients=2,
                    ) as process:
                        stdout, stderr = process.communicate(timeout=18)
                        assert process.returncode == 0, (stdout[-2500:], stderr[-2500:])
                        assert '"metric":"http_reqs"' in stdout
                assert len(observed) == prior_count + 1

            slow = ManagedEgress(origin, "127.0.0.1", max_rps=1, max_active=1, max_seconds=10)

            def request_slow():
                try:
                    slow.request("GET", "/slow", {}, b"")
                except (OSError, http.client.HTTPException):
                    stopped.set()

            active = threading.Thread(target=request_slow, daemon=True)
            active.start()
            assert blocking.wait(timeout=2)
            with pytest.raises(EgressDenied, match="connection limit"):
                slow.request("GET", "/checkout", {}, b"")
            slow.close()
            assert stopped.wait(timeout=2)
            active.join(timeout=2)
        finally:
            release.set()
            server.shutdown()
            thread.join()


@pytest.mark.parametrize("path,headers", [
    ("https://other.test/", {}),
    ("//other.test/", {}),
    ("/path", {"Host": "other.test"}),
    ("/path", {"Connection": "keep-alive"}),
])
def test_egress_rejects_alternate_destinations_before_connecting(path, headers):
    broker = ManagedEgress("https://approved.test", "127.0.0.1",
                          max_rps=1, max_active=1, max_seconds=1)
    with pytest.raises(EgressDenied):
        broker.request("GET", path, headers, b"")



def test_worker_message_cannot_set_the_destination():
    from perfagent.runner.worker_bridge import _dispatch

    broker = ManagedEgress("https://approved.test", "127.0.0.1",
                          max_rps=1, max_active=1, max_seconds=1)
    with pytest.raises(ValueError, match="request fields"):
        _dispatch(broker, {"method": "GET", "path": "/", "headers": {}, "body": "",
                           "origin": "https://other.test"})
