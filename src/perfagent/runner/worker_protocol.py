"""Request limits and result types shared by the broker and worker."""

from dataclasses import dataclass

HOP_HEADERS = {
    "connection",
    "content-length",
    "expect",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
MAX_HTTP_BODY_BYTES = 1024 * 1024
MAX_SUMMARY_BYTES = 2 * 1024 * 1024
WORKER_SUMMARY_TYPE = "PerfAgentWorkerSummary"


class EgressDenied(ValueError):
    """The worker request is outside the configured policy."""


@dataclass(frozen=True)
class BrokerResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
