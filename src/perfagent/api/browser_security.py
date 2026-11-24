"""Protect browser writes and set baseline response headers."""

from starlette.datastructures import Headers, MutableHeaders, URL
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from perfagent.config import get_settings

_READ_METHODS = {"GET", "HEAD", "OPTIONS"}


class BrowserWriteProtection:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Content-Type-Options"] = "nosniff"
                response_headers["X-Frame-Options"] = "DENY"
                response_headers["Referrer-Policy"] = "same-origin"
                if response_headers.get("content-type", "").startswith("application/json"):
                    response_headers["Cache-Control"] = "no-store"
            await send(message)

        if scope["method"] in _READ_METHODS:
            await self.app(scope, receive, secure_send)
            return

        headers = Headers(scope=scope)
        origins = headers.getlist("origin")
        if origins:
            url = URL(scope=scope)
            own_origin = f"{url.scheme}://{url.netloc}"
            trusted = get_settings().perfagent_trusted_browser_origins
            permitted = len(origins) == 1 and origins[0] != "null" and (
                origins[0] == own_origin or origins[0] in trusted
            )
        else:
            # CLI clients send no Fetch Metadata. Browser requests marked as coming
            # from another origin need an explicit, trusted Origin.
            permitted = headers.get("sec-fetch-site") in (None, "same-origin", "none")

        if not permitted:
            response = JSONResponse(
                {"detail": "This browser origin is not allowed to modify PerfAgent."},
                status_code=403,
            )
            await response(scope, receive, secure_send)
            return
        await self.app(scope, receive, secure_send)
