"""Authenticate managed workspace requests at the trusted gateway boundary."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from perfagent.config import get_settings


PUBLIC_PAGES = frozenset({"/", "/demo", "/sign-in", "/sign-up"})
PUBLIC_ASSET = re.compile(r"/assets/[a-zA-Z0-9_.-]+\.(?:js|css|png|jpg|svg|woff2?)")

MANAGED_EXECUTION_DETAIL = "Execution is unavailable in managed workspaces until an isolated runner is configured."


def managed_execution_blocked() -> bool:
    return get_settings().perfagent_access_mode == "managed"


def require_local_execution() -> None:
    if managed_execution_blocked():
        raise HTTPException(status_code=403, detail=MANAGED_EXECUTION_DETAIL)


@dataclass(frozen=True)
class Principal:
    subject: str


def _single_header(headers: Headers, name: str) -> str | None:
    values = headers.getlist(name)
    return values[0] if len(values) == 1 else None


class WorkspaceAccess:
    """Accept identity assertions only from the configured authentication gateway."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        config = get_settings()
        if config.perfagent_access_mode == "local":
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return

        path = scope["path"]
        if scope["method"] in {"GET", "HEAD"} and (path in PUBLIC_PAGES or PUBLIC_ASSET.fullmatch(path)):
            await self.app(scope, receive, send)
            return

        expected = config.perfagent_gateway_secret.get_secret_value()
        allowed = config.perfagent_workspace_members
        headers = Headers(scope=scope)
        supplied = _single_header(headers, "x-perfagent-gateway-secret") or ""
        subject = _single_header(headers, "x-perfagent-subject")
        assurance = _single_header(headers, "x-perfagent-assurance")

        if len(expected) < 32 or not allowed:
            status, detail = 503, "Managed access is not configured."
        elif not secrets.compare_digest(supplied.encode(), expected.encode()) or not subject:
            status, detail = 401, "Sign in through the PerfAgent gateway."
        elif subject not in allowed or assurance != "mfa":
            status, detail = 403, "Workspace membership and multi-factor sign-in are required."
        else:
            scope.setdefault("state", {})["principal"] = Principal(subject)
            # Gateway credentials terminate here and never reach API handlers.
            gateway_headers = {b"x-perfagent-gateway-secret", b"x-perfagent-subject", b"x-perfagent-assurance"}
            scope = {**scope, "headers": [(key, value) for key, value in scope["headers"]
                                        if key.lower() not in gateway_headers]}
            await self.app(scope, receive, send)
            return

        await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
