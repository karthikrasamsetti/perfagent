"""Import endpoints from OpenAPI/Swagger, Postman collections, and HAR captures.

All three parsers normalize to the same shape — a list of ImportedEndpoint — so the
UI and planner treat them identically. This removes the "type every endpoint by
hand" step for real APIs.

  - OpenAPI/Swagger: structured spec -> every path+method, with a sample body from
    the request schema when present.
  - Postman: a collection's requests -> method, path, body.
  - HAR: a recorded browser/API session -> the real requests that happened (and, as a
    bonus, their order, which later helps correlation).

Deterministic, no LLM. The target base URL is also inferred where possible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass
class ImportedEndpoint:
    method: str
    path: str
    example_body: dict | None = None
    description: str = ""


@dataclass
class ImportResult:
    source: str
    base_url: str = ""
    endpoints: list[ImportedEndpoint] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "base_url": self.base_url,
            "warnings": self.warnings,
            "endpoints": [
                {
                    "method": e.method,
                    "path": e.path,
                    "example_body": e.example_body,
                    "description": e.description,
                }
                for e in self.endpoints
            ],
        }


class ImportError_(ValueError):
    """Raised when a file can't be parsed as the detected/declared format."""


_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


# ---------- format detection ----------

def detect_format(filename: str, content: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".har"):
        return "har"
    stripped = content.lstrip()
    try:
        obj = json.loads(stripped) if stripped.startswith(("{", "[")) else None
    except json.JSONDecodeError:
        obj = None
    if isinstance(obj, dict):
        if "openapi" in obj or "swagger" in obj:
            return "openapi"
        if "log" in obj and isinstance(obj.get("log"), dict) and "entries" in obj["log"]:
            return "har"
        info = obj.get("info", {})
        if isinstance(info, dict) and ("_postman_id" in info or "schema" in info) and "item" in obj:
            return "postman"
    # yaml-ish openapi
    if "openapi:" in content[:200] or "swagger:" in content[:200]:
        return "openapi_yaml"
    return "unknown"


# ---------- OpenAPI / Swagger ----------

def _sample_from_schema(schema: dict, depth: int = 0) -> object:
    """Produce a tiny example value from a JSON schema (best effort)."""
    if not isinstance(schema, dict) or depth > 4:
        return None
    if "example" in schema:
        return schema["example"]
    t = schema.get("type")
    if t == "object" or "properties" in schema:
        out = {}
        for k, v in (schema.get("properties") or {}).items():
            out[k] = _sample_from_schema(v, depth + 1)
        return out
    if t == "array":
        item = _sample_from_schema(schema.get("items", {}), depth + 1)
        return [item] if item is not None else []
    if t == "integer" or t == "number":
        return 0
    if t == "boolean":
        return True
    if t == "string":
        return schema.get("default", "string")
    return None


def _load_spec(content: str) -> dict:
    """Parse an OpenAPI spec that may be JSON or YAML."""
    stripped = content.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ImportError_(f"OpenAPI JSON is invalid: {e}") from e
    # try YAML
    try:
        import yaml
    except ImportError as e:
        raise ImportError_(
            "this looks like YAML — install pyyaml (uv add pyyaml) or convert the spec to JSON"
        ) from e
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ImportError_(f"OpenAPI YAML is invalid: {e}") from e
    if not isinstance(data, dict):
        raise ImportError_("OpenAPI spec must be a mapping")
    return data


def parse_openapi(content: str) -> ImportResult:
    spec = _load_spec(content)
    res = ImportResult(source="openapi")

    # base url from servers (OAS3) or host+basePath (Swagger2)
    servers = spec.get("servers")
    if isinstance(servers, list) and servers and isinstance(servers[0], dict):
        res.base_url = str(servers[0].get("url", "")).rstrip("/")
    elif spec.get("host"):
        scheme = (spec.get("schemes") or ["https"])[0]
        res.base_url = f"{scheme}://{spec['host']}{spec.get('basePath', '')}".rstrip("/")

    paths = spec.get("paths", {})
    if not isinstance(paths, dict) or not paths:
        raise ImportError_("OpenAPI spec has no paths")

    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in _METHODS or not isinstance(op, dict):
                continue
            body = None
            # OAS3 requestBody
            rb = op.get("requestBody", {})
            if isinstance(rb, dict):
                content_obj = rb.get("content", {})
                appjson = content_obj.get("application/json", {})
                schema = appjson.get("schema")
                if schema:
                    sample = _sample_from_schema(schema)
                    if isinstance(sample, dict):
                        body = sample
            # Swagger2 body parameter
            if body is None:
                for p in op.get("parameters", []) or []:
                    if isinstance(p, dict) and p.get("in") == "body" and p.get("schema"):
                        sample = _sample_from_schema(p["schema"])
                        if isinstance(sample, dict):
                            body = sample
            res.endpoints.append(ImportedEndpoint(
                method=method.upper(), path=path,
                example_body=body,
                description=str(op.get("summary") or op.get("operationId") or "")[:120],
            ))
    if not res.endpoints:
        raise ImportError_("no operations found in the OpenAPI spec")
    return res


# ---------- Postman collection ----------

def _postman_url_path(url) -> str:
    """Postman url may be a string or an object with 'path' list / 'raw'."""
    if isinstance(url, str):
        sp = urlsplit(url)
        return sp.path or "/"
    if isinstance(url, dict):
        if isinstance(url.get("path"), list):
            return "/" + "/".join(str(p).strip("/") for p in url["path"] if p is not None)
        raw = url.get("raw", "")
        return urlsplit(raw).path or "/"
    return "/"


def _postman_base(url) -> str:
    raw = url if isinstance(url, str) else (url.get("raw", "") if isinstance(url, dict) else "")
    sp = urlsplit(raw)
    if sp.scheme and sp.netloc:
        return f"{sp.scheme}://{sp.netloc}"
    return ""


def parse_postman(content: str) -> ImportResult:
    try:
        col = json.loads(content)
    except json.JSONDecodeError as e:
        raise ImportError_(f"Postman collection must be JSON: {e}") from e
    res = ImportResult(source="postman")

    def walk(items):
        for it in items or []:
            if not isinstance(it, dict):
                continue
            if "item" in it:          # folder
                walk(it["item"])
                continue
            req = it.get("request")
            if not isinstance(req, dict):
                continue
            method = str(req.get("method", "GET")).upper()
            url = req.get("url", "")
            path = _postman_url_path(url)
            if not res.base_url:
                res.base_url = _postman_base(url)
            body = None
            b = req.get("body", {})
            if isinstance(b, dict) and b.get("mode") == "raw" and b.get("raw"):
                try:
                    parsed = json.loads(b["raw"])
                    if isinstance(parsed, dict):
                        body = parsed
                except json.JSONDecodeError:
                    pass
            res.endpoints.append(ImportedEndpoint(
                method=method, path=path, example_body=body,
                description=str(it.get("name", ""))[:120],
            ))

    walk(col.get("item", []))
    if not res.endpoints:
        raise ImportError_("no requests found in the Postman collection")
    return res


# ---------- HAR ----------

def parse_har(content: str) -> ImportResult:
    try:
        har = json.loads(content)
    except json.JSONDecodeError as e:
        raise ImportError_(f"HAR must be JSON: {e}") from e
    res = ImportResult(source="har")
    entries = (har.get("log", {}) or {}).get("entries", [])
    if not entries:
        raise ImportError_("HAR has no entries")

    seen = set()
    for en in entries:
        req = en.get("request", {})
        method = str(req.get("method", "GET")).upper()
        url = req.get("url", "")
        sp = urlsplit(url)
        path = sp.path or "/"
        # only keep API-ish calls (skip static assets)
        if any(path.endswith(ext) for ext in
               (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".woff2", ".ico", ".map")):
            continue
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        if not res.base_url and sp.scheme and sp.netloc:
            res.base_url = f"{sp.scheme}://{sp.netloc}"
        body = None
        pd = req.get("postData", {})
        if isinstance(pd, dict) and pd.get("text"):
            try:
                parsed = json.loads(pd["text"])
                if isinstance(parsed, dict):
                    body = parsed
            except json.JSONDecodeError:
                pass
        res.endpoints.append(ImportedEndpoint(method=method, path=path, example_body=body))
    if not res.endpoints:
        raise ImportError_("no API requests found in the HAR (only static assets?)")
    return res


# ---------- dispatch ----------

def import_endpoints(filename: str, content: str, fmt: str | None = None) -> ImportResult:
    """Parse endpoints from content. Format auto-detected unless given."""
    if not content.strip():
        raise ImportError_("file is empty")
    fmt = fmt or detect_format(filename, content)
    if fmt == "openapi":
        return parse_openapi(content)
    if fmt == "openapi_yaml":
        return parse_openapi(content)
    if fmt == "postman":
        return parse_postman(content)
    if fmt == "har":
        return parse_har(content)
    raise ImportError_(
        "could not detect format — expected OpenAPI JSON, a Postman collection, or a .har file"
    )