"""Redaction engine — scrubs sensitive data before it reaches the LLM.

Two kinds of masking:
  - ONE-WAY (secret): truly sensitive values (API keys, tokens, card numbers,
    passwords, emails, query-string secrets) are replaced with a fixed placeholder
    and NEVER restored. The LLM never sees them and neither does anything downstream.
  - REVERSIBLE (identifier): non-sensitive-but-private identifiers (any hostname in a
    URL, internal hostnames, private IPs) are replaced with stable placeholders that
    CAN be mapped back after the LLM responds, so reports read naturally.

The deterministic core keeps the real data; the LLM only ever sees redacted text.
URL paths ARE sent to the LLM (it needs them to plan journeys); hosts are masked and
query-string secrets are stripped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---- detectors -------------------------------------------------------------

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")
_APIKEY = re.compile(
    r"\b(?:sk-|pk-|rk-|api[_-]?key[_-]?|bearer\s+)[A-Za-z0-9_\-]{16,}\b", re.IGNORECASE
)
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# ${field} template placeholders — references filled from a data file, not secrets.
_PLACEHOLDER = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}")

# Any URL — we mask the HOST (reversible) and strip query-string secrets.
_URL = re.compile(r"\bhttps?://([A-Za-z0-9.\-:]+)(/[^\s\"'<>]*)?", re.IGNORECASE)

# Internal hostnames / private IPs that may appear OUTSIDE a URL (bare).
_INTERNAL_HOST = re.compile(
    r"\b(?:[a-z0-9-]+\.)+(?:internal|local|corp|intra|svc)\b", re.IGNORECASE
)
_PRIVATE_IP = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)

# Secrets inside a URL query string, e.g. ?token=abc&api_key=xyz
_QUERY_SECRET = re.compile(
    r"([?&](?:token|access_token|refresh_token|api[_-]?key|key|secret|"
    r"client_secret|password|pwd|auth|sig|signature|session)"
    r"=)([^&\s\"'<>]+)",
    re.IGNORECASE,
)

# Inline "secret_key = value" or "secret_key: value" in free text (one-way).
_INLINE_SECRET = re.compile(
    r'["\']?\b(password|passwd|pwd|secret|token|access_token|refresh_token|api[_-]?key|'
    r'authorization|client_secret|private_key)\b["\']?'
    r"(\s*[=:]\s*)"
    r'("[^"]*"|\'[^\']*\'|[^\s,;&}]+)',
    re.IGNORECASE,
)

# Detectors applied after URL handling. (name, pattern, mode)
_DETECTORS: list[tuple[str, re.Pattern, str]] = [
    ("JWT", _JWT, "secret"),
    ("APIKEY", _APIKEY, "secret"),
    ("EMAIL", _EMAIL, "secret"),
    ("SSN", _SSN, "secret"),
    ("CARD", _CARD, "secret"),
    ("HOST", _INTERNAL_HOST, "identifier"),
    ("PRIVATE_IP", _PRIVATE_IP, "identifier"),
]

# Field names whose *values* are always secret regardless of content.
_SECRET_KEYS = {
    "password", "passwd", "pwd", "secret", "token", "access_token",
    "refresh_token", "api_key", "apikey", "authorization", "auth",
    "client_secret", "private_key", "session", "cookie",
}


@dataclass
class RedactionResult:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)


def _luhn_ok(digits: str) -> bool:
    nums = [int(c) for c in digits if c.isdigit()]
    if not (13 <= len(nums) <= 19):
        return False
    total, parity = 0, len(nums) % 2
    for i, n in enumerate(nums):
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def redact_text(text: str, counts: dict[str, int] | None = None,
                mapping: dict[str, str] | None = None) -> str:
    """Redact a single string. Mutates the shared counts/mapping if provided.

    ${field} template placeholders are NOT secrets — they are references filled from
    a data file at run time. We shield them from redaction so e.g. "${password}"
    survives instead of being masked as if it were a real password.
    """
    if counts is None:
        counts = {}
    if mapping is None:
        mapping = {}
    id_index: dict[str, str] = {v: k for k, v in mapping.items()}

    # Shield ${field} placeholders behind sentinels before any detector runs,
    # then restore them at the end. They contain no real data.
    _shield: dict[str, str] = {}

    def _shield_repl(m: re.Match) -> str:
        token = f"\x00PH{len(_shield)}\x00"
        _shield[token] = m.group(0)
        return token

    text = _PLACEHOLDER.sub(_shield_repl, text)

    def _host_placeholder(host: str) -> str:
        # strip any :port for the mapping key, keep it on the placeholder output
        if host in id_index:
            return id_index[host]
        n = len([k for k in mapping if k.startswith("<HOST_")]) + 1
        placeholder = f"<HOST_{n}>"
        mapping[placeholder] = host
        id_index[host] = placeholder
        return placeholder

    # 0. Strip secrets inside URL query strings first (one-way).
    def _query_repl(m: re.Match) -> str:
        counts["QUERY_SECRET"] = counts.get("QUERY_SECRET", 0) + 1
        return f"{m.group(1)}<QUERY_SECRET_REDACTED>"

    text = _QUERY_SECRET.sub(_query_repl, text)

    # 1. Mask the HOST of every URL (reversible), keep scheme + path.
    def _url_repl(m: re.Match) -> str:
        host = m.group(1)
        path = m.group(2) or ""
        counts["URL_HOST"] = counts.get("URL_HOST", 0) + 1
        scheme = m.group(0).split("://", 1)[0]
        return f"{scheme}://{_host_placeholder(host)}{path}"

    text = _URL.sub(_url_repl, text)

    # 2. Inline "secret_key = value" pairs — keep the key, redact the value.
    #    But if the value is a shielded ${placeholder}, leave it alone.
    def _inline_repl(m: re.Match) -> str:
        full = m.group(0)
        value = m.group(3)
        if "\x00PH" in value:            # value is a shielded placeholder — not a secret
            return full
        counts["INLINE_SECRET"] = counts.get("INLINE_SECRET", 0) + 1
        prefix = full[: full.rfind(value)]
        return f"{prefix}<FIELD_REDACTED>"

    text = _INLINE_SECRET.sub(_inline_repl, text)

    # 3. Remaining detectors (bare emails, tokens, cards, bare internal hosts, IPs).
    def _sub(name: str, mode: str):
        def repl(m: re.Match) -> str:
            val = m.group(0)
            if name == "CARD" and not _luhn_ok(val):
                return val
            counts[name] = counts.get(name, 0) + 1
            if mode == "secret":
                return f"<{name}_REDACTED>"
            if val in id_index:
                return id_index[val]
            placeholder = f"<{name}_{len([k for k in mapping if k.startswith('<'+name)])+1}>"
            mapping[placeholder] = val
            id_index[val] = placeholder
            return placeholder
        return repl

    for name, pattern, mode in _DETECTORS:
        text = pattern.sub(_sub(name, mode), text)

    # Restore the shielded ${field} placeholders.
    for token, original in _shield.items():
        text = text.replace(token, original)
    return text


def redact_value(value, counts: dict[str, int], mapping: dict[str, str], key: str | None = None):
    """Recursively redact a JSON-like value (dict/list/str/other)."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            # A ${field} placeholder value is a template reference, not a secret —
            # leave it untouched even if the key name looks sensitive.
            is_placeholder = isinstance(v, str) and _PLACEHOLDER.fullmatch(v.strip()) is not None
            if (
                isinstance(k, str)
                and k.lower() in _SECRET_KEYS
                and isinstance(v, (str, int, float))
                and not is_placeholder
            ):
                counts["FIELD"] = counts.get("FIELD", 0) + 1
                out[k] = "<FIELD_REDACTED>"
            else:
                out[k] = redact_value(v, counts, mapping, key=k)
        return out
    if isinstance(value, list):
        return [redact_value(v, counts, mapping) for v in value]
    if isinstance(value, str):
        return redact_text(value, counts, mapping)
    return value


def redact(obj) -> RedactionResult:
    """Redact a string or JSON-like object. Returns redacted copy + reversible map."""
    counts: dict[str, int] = {}
    mapping: dict[str, str] = {}
    if isinstance(obj, str):
        red = redact_text(obj, counts, mapping)
    else:
        red = redact_value(obj, counts, mapping)
    return RedactionResult(text=red, mapping=mapping, counts=counts)


def restore(text: str, mapping: dict[str, str]) -> str:
    """Map reversible identifier placeholders back to their originals."""
    for placeholder, original in mapping.items():
        text = text.replace(placeholder, original)
    return text