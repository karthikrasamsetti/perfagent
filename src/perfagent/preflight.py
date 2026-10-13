"""Pre-flight check — fire ONE request per endpoint and report the status.

Before a full load run, this sends a single request to each endpoint (with the
configured headers and a sample data row if present) and reports the HTTP status.
It catches "this data/auth produces errors" before you waste a full run — answering
"will we get valid responses?".

Deterministic, no LLM. Uses httpx with a short timeout. Never generates load — it is
exactly one request per endpoint.
"""

from __future__ import annotations

import json

import httpx

from perfagent.contracts.load_model import LoadModel


def _fill_placeholders(text: str, row: dict | None) -> str:
    """Replace ${field} with a sample row value (or leave as-is if no data)."""
    if not row:
        return text
    out = text
    for k, v in row.items():
        out = out.replace("${" + k + "}", str(v))
    return out


def _fill_body(body: dict | None, row: dict | None) -> dict | None:
    if not body:
        return body
    raw = json.dumps(body)
    raw = _fill_placeholders(raw, row)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return body


def preflight(model: LoadModel, sample_row: dict | None = None,
              timeout: float = 5.0) -> dict:
    """Send one request per unique endpoint. Returns a summary with per-endpoint status."""
    base = model.target_base_url.rstrip("/")
    headers = dict(getattr(model, "headers", {}) or {})

    # collect unique (method, path) pairs across all scenarios/steps
    seen = set()
    endpoints = []
    for sc in model.scenarios:
        for st in sc.steps:
            key = (st.method.value, st.path)
            if key in seen:
                continue
            seen.add(key)
            endpoints.append(st)

    results = []
    ok_count = 0
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for st in endpoints:
            method = st.method.value
            path = _fill_placeholders(st.path, sample_row)
            url = base + path
            body = _fill_body(st.body, sample_row)
            req_headers = dict(headers)
            try:
                if method in ("GET", "DELETE"):
                    resp = client.request(method, url, headers=req_headers)
                else:
                    req_headers.setdefault("Content-Type", "application/json")
                    resp = client.request(method, url, headers=req_headers,
                                          content=json.dumps(body or {}))
                status = resp.status_code
                ok = 200 <= status < 400
                results.append({
                    "method": method, "path": st.path, "status": status,
                    "ok": ok, "error": "",
                })
                if ok:
                    ok_count += 1
            except Exception as e:  # noqa: BLE001
                results.append({
                    "method": method, "path": st.path, "status": None,
                    "ok": False, "error": type(e).__name__ + ": " + str(e)[:120],
                })

    total = len(results)
    return {
        "total": total,
        "ok": ok_count,
        "failed": total - ok_count,
        "all_ok": ok_count == total and total > 0,
        "results": results,
    }
