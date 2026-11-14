"""Request data — where each value in a request comes from, and what it looks like.

A request body mixes three kinds of value (see README "Dynamic test data"):

    fixed       a constant                      "serviceCode": "GRND"
    file        a column of the data file       "branch": "${branch}"
    generated   made fresh for every request    "orderId": "${uuid}"

(plus "captured": a value taken from an earlier response, e.g. "${token}").

This module is the Python side of that: it classifies every field of a body, and it
can fill a body in with a real data row and sample generated values — so the UI can
show "this is what will be sent" before anything runs, and the pre-flight check
sends realistic requests instead of literal "${uuid}" text.

Everything here is deterministic string work. No LLM, and nothing here sends a request.
The values it generates are SAMPLES of the same kind the k6 script generates at run
time (generator/generators.py); they are not the values a run will use.
"""

from __future__ import annotations

import json
import random
import re
import string
import time
import uuid
from datetime import datetime, timedelta, timezone

from perfagent.generator.generators import is_generator

_TOKEN = re.compile(r"\$\{([^}]+)\}")
_WHOLE_TOKEN = re.compile(r"^\$\{([^}]+)\}$")

# ---------- sample values for generators (mirror generator/generators.py) ----------

_FIRST = ["James", "Mary", "John", "Patricia", "Robert", "Maria", "Chen", "Omar", "Raj", "Priya"]
_LAST = ["Smith", "Johnson", "Garcia", "Miller", "Lee", "Kim", "Patel", "Nguyen", "Khan", "Silva"]
_COMPANY = ["Acme", "Globex", "Initech", "Umbrella", "Stark", "Wayne", "Hooli", "Pied Piper"]
_PHRASE = ["Streamlined zero-tolerance core", "Robust tertiary synergy",
           "Scalable realtime interface", "User-centric agile hub"]
_CITY = ["Phoenix", "Austin", "Denver", "Seattle", "Miami", "Boston", "Chicago", "Dallas"]
_STATE = ["AZ", "TX", "CO", "WA", "FL", "MA", "IL", "CA"]
_STREET = ["Main St", "Oak Ave", "Pine Rd", "Maple Dr", "Cedar Ln", "Elm St"]

_RANDOM_INT = re.compile(r"^randomInt\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)$")
_RANDOM_STR = re.compile(r"^randomString\(\s*(\d+)\s*\)$")
_RANDOM_FROM = re.compile(r"^randomFrom\((.+)\)$")
_DATE_OFFSET = re.compile(
    r"^dateOffset\(\s*(-?\d+)\s*,\s*['\"]?(day|days|hour|hours|minute|minutes)['\"]?\s*\)$")


def _rand_text(n: int, rng: random.Random) -> str:
    return "".join(rng.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def sample_generator(token: str, rng: random.Random | None = None, index: int = 0):
    """A sample value for a generator token (the text inside ${...}).

    Returns None if the token is not a generator. ``index`` stands in for the
    request number, so ${sequential}/${iter} differ between samples.
    """
    rng = rng or random
    t = token.strip()
    simple = {
        "uuid": lambda: str(uuid.UUID(int=rng.getrandbits(128), version=4)),
        "randomFullName": lambda: f"{rng.choice(_FIRST)} {rng.choice(_LAST)}",
        "randomFirstName": lambda: rng.choice(_FIRST),
        "randomLastName": lambda: rng.choice(_LAST),
        "randomCompanyName": lambda: f"{rng.choice(_COMPANY)} {rng.choice(['Inc', 'LLC', 'Corp'])}",
        "randomCatchPhrase": lambda: rng.choice(_PHRASE),
        "randomCity": lambda: rng.choice(_CITY),
        "randomState": lambda: rng.choice(_STATE),
        "randomStreetAddress": lambda: f"{rng.randint(100, 9999)} {rng.choice(_STREET)}",
        "randomZipCode": lambda: str(rng.randint(10000, 99999)),
        "randomPhone": lambda: f"({rng.randint(200, 999)}) {rng.randint(200, 999)}-"
                               f"{rng.randint(0, 9999):04d}",
        "randomBic": lambda: "".join(rng.choice(string.ascii_uppercase) for _ in range(8)),
        "randomBankAccountBic": lambda: "".join(
            rng.choice(string.ascii_uppercase) for _ in range(8)),
        "randomEmail": lambda: f"user_{_rand_text(8, rng)}@loadtest.test",
        "timestamp": lambda: int(time.time() * 1000) + index,
        "sequential": lambda: 1_000_000 + index,
        "vu": lambda: 1,
        "iter": lambda: index,
    }
    if t in simple:
        return simple[t]()
    m = _RANDOM_INT.match(t)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
        return rng.randint(lo, hi)
    m = _RANDOM_STR.match(t)
    if m:
        return _rand_text(int(m.group(1)), rng)
    m = _DATE_OFFSET.match(t)
    if m:
        n, unit = int(m.group(1)), m.group(2).rstrip("s")
        delta = {"day": timedelta(days=n), "hour": timedelta(hours=n),
                 "minute": timedelta(minutes=n)}[unit]
        return (datetime.now(timezone.utc) + delta).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z")
    m = _RANDOM_FROM.match(t)
    if m:
        parts = [p.strip().strip("\"'") for p in m.group(1).split(",")]
        choice = rng.choice(parts)
        return (float(choice) if "." in choice else int(choice)) \
            if re.fullmatch(r"-?\d+(\.\d+)?", choice) else choice
    return None


# ---------- classify ----------

def classify_value(value, columns: list[str] | tuple[str, ...] = ()) -> dict:
    """Where one leaf value comes from.

    Returns {"source": fixed|file|generated|captured|mixed, "token": inner text of a
    lone ${...} (or ""), "tokens": every inner token found}.
    """
    if not isinstance(value, str):
        return {"source": "fixed", "token": "", "tokens": []}
    tokens = [t.strip() for t in _TOKEN.findall(value)]
    if not tokens:
        return {"source": "fixed", "token": "", "tokens": []}
    whole = _WHOLE_TOKEN.match(value.strip())
    if not whole:
        return {"source": "mixed", "token": "", "tokens": tokens}   # e.g. "user-${id}"
    token = whole.group(1).strip()
    if is_generator(token):
        source = "generated"
    elif token in columns:
        source = "file"
    else:
        source = "captured"      # a value captured from an earlier response (or unknown)
    return {"source": source, "token": token, "tokens": tokens}


def flatten(body, prefix: str = "") -> list[tuple[str, object]]:
    """Every leaf of a JSON body as (path, value): a.b, items[0].sku …"""
    out: list[tuple[str, object]] = []
    if isinstance(body, dict):
        if not body and prefix:
            out.append((prefix, body))
        for k, v in body.items():
            out.extend(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(body, list):
        if not body and prefix:
            out.append((prefix, body))
        for i, v in enumerate(body):
            out.extend(flatten(v, f"{prefix}[{i}]"))
    else:
        out.append((prefix, body))
    return out


def describe_fields(body, columns: list[str] | tuple[str, ...] = ()) -> list[dict]:
    """Every field of a body with its source — what the request-data table shows."""
    return [{"path": path, "value": value, **classify_value(value, columns)}
            for path, value in flatten(body)]


# ---------- fill in ----------

def _resolve_token(token: str, row: dict | None, rng: random.Random, index: int):
    """(found, value) for one inner token: a generator sample or a data-row value."""
    if is_generator(token):
        value = sample_generator(token, rng, index)
        if value is not None:
            return True, value
    if row is not None and token in row:
        return True, row[token]
    return False, None            # captured variable: only known at run time


def resolve_text(text: str, row: dict | None = None, rng: random.Random | None = None,
                 index: int = 0):
    """Fill the ${...} tokens of one string.

    A string that is exactly one token keeps the value's own type (a number stays a
    number); tokens inside longer text are substituted as text. Tokens that cannot be
    known before the run (captured variables) are left as they are.
    """
    rng = rng or random
    whole = _WHOLE_TOKEN.match(text.strip())
    if whole:
        found, value = _resolve_token(whole.group(1).strip(), row, rng, index)
        return value if found else text

    def _sub(m: re.Match) -> str:
        found, value = _resolve_token(m.group(1).strip(), row, rng, index)
        return str(value) if found else m.group(0)

    return _TOKEN.sub(_sub, text)


def resolve(value, row: dict | None = None, rng: random.Random | None = None, index: int = 0):
    """Fill every ${...} token in a JSON value (dict / list / leaf)."""
    rng = rng or random
    if isinstance(value, dict):
        return {k: resolve(v, row, rng, index) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, row, rng, index) for v in value]
    if isinstance(value, str):
        return resolve_text(value, row, rng, index)
    return value


def unresolved_tokens(value) -> list[str]:
    """Tokens still present after resolve() — values only known while the test runs."""
    found = _TOKEN.findall(json.dumps(value)) if not isinstance(value, str) \
        else _TOKEN.findall(value)
    seen: list[str] = []
    for t in (x.strip() for x in found):
        if t not in seen:
            seen.append(t)
    return seen


# ---------- rows ----------

def pick_rows(rows: list[dict], count: int, row_mode: str = "random",
              rng: random.Random | None = None) -> list[dict | None]:
    """The rows the first ``count`` requests would get, for a preview.

    random -> any rows; sequential/unique -> the first rows in file order (unique
    stops when the file runs out, exactly as the run does).
    """
    rng = rng or random
    if not rows:
        return [None] * count
    if row_mode == "random":
        return [rng.choice(rows) for _ in range(count)]
    if row_mode == "unique":
        return list(rows[:count])
    return [rows[i % len(rows)] for i in range(count)]


# ---------- preview ----------

def preview_requests(model, rows: list[dict] | None = None, samples: int = 3,
                     seed: int | None = None) -> dict:
    """What the first few requests of each step will look like.

    ``model`` is a LoadModel; ``rows`` are the data file's parsed rows (or None).
    Returns {"steps": [...], "row_mode", "rows_available"}; each step lists its
    sample requests (method, url, body), the values that can only be known during the
    run (captured from an earlier response), and any ${name} that has no source.
    """
    from perfagent.generator.k6_corr import captured_vars

    rng = random.Random(seed)
    rows = rows or []
    captured = captured_vars(model)
    row_mode = model.data_file.row_mode if model.data_file else "random"
    columns = list(model.data_file.fields) if model.data_file else []
    base = model.target_base_url.rstrip("/")
    samples = max(1, min(int(samples), 10))

    steps = []
    for si, sc in enumerate(model.scenarios):
        chosen = pick_rows(rows, samples, row_mode, rng)
        for sti, st in enumerate(sc.steps):
            dynamic = bool(_TOKEN.search(st.path)) or bool(
                st.body and _TOKEN.search(json.dumps(st.body)))
            requests = []
            for i, row in enumerate(chosen):
                path = resolve_text(st.path, row, rng, i)
                body = resolve(st.body, row, rng, i) if st.body else None
                requests.append({
                    "method": st.method.value,
                    "url": base + str(path),
                    "body": body,
                    "row_number": (rows.index(row) + 1) if row is not None and row in rows
                    else None,
                })
                if not dynamic:
                    break                       # a fixed request looks the same every time
            pending = unresolved_tokens(
                [requests[0]["url"], requests[0]["body"]]) if requests else []
            # A token that is neither generated, nor a file column, nor captured from
            # an earlier response has no source at all: the script would send it empty.
            undefined = [t for t in pending if t.split("(")[0] not in captured]
            steps.append({
                "scenario": sc.name, "scenario_index": si, "step_index": sti,
                "name": st.name, "method": st.method.value, "path": st.path,
                "dynamic": dynamic,
                "fields": describe_fields(st.body, columns) if st.body else [],
                "requests": requests,
                "run_time_values": [t for t in pending if t not in undefined],
                "undefined": undefined,
            })
    return {
        "row_mode": row_mode,
        "rows_available": len(rows),
        "samples": samples,
        "steps": steps,
    }


__all__ = [
    "sample_generator", "classify_value", "flatten", "describe_fields", "resolve",
    "resolve_text", "unresolved_tokens", "pick_rows", "preview_requests",
]
