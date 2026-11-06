"""Dynamic data generators — produce a fresh, often-unique value per request.

A data file gives *existing* values (one row per VU). Generators give *new* values
created at run time — essential for real write-endpoints (unique signups, new order
ids, timestamps). They are written in bodies/paths with the same ${...} syntax:

    ${uuid}                 -> a random UUID (unique per request)
    ${randomInt(1,100)}     -> a random integer in [1,100]
    ${randomEmail}          -> user_<rand>@loadtest.test
    ${randomString(8)}      -> an 8-char random string
    ${timestamp}            -> current epoch milliseconds
    ${sequential}           -> unique per VU+iteration (__VU * 1e6 + __ITER)
    ${randomFrom(a,b,c)}    -> a random choice from the given list
    ${vu} / ${iter}         -> k6's __VU / __ITER

The renderer turns each into a k6 JS expression. Deterministic — no LLM.
"""

from __future__ import annotations

import re

# token name -> k6 JS expression (evaluated fresh each time it's referenced)
_SIMPLE = {
    "uuid": "uuidv4()",
    "randomFullName": "fakeName()",
    "randomFirstName": "fakeFirstName()",
    "randomLastName": "fakeLastName()",
    "randomCompanyName": "fakeCompany()",
    "randomCatchPhrase": "fakeCatchPhrase()",
    "randomCity": "fakeCity()",
    "randomStreetAddress": "fakeStreet()",
    "randomPhone": "fakePhone()",
    "randomBic": "fakeBic()",
    "randomBankAccountBic": "fakeBic()",
    "randomZipCode": "fakeZip()",
    "randomState": "fakeState()",
    "randomEmail": "`user_${Math.random().toString(36).slice(2,10)}@loadtest.test`",
    "timestamp": "Date.now()",
    "sequential": "(__VU * 1000000 + __ITER)",
    "vu": "__VU",
    "iter": "__ITER",
}

# generators that take arguments, matched by regex -> a function producing the JS
_RANDOM_INT = re.compile(r"^randomInt\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)$")
_RANDOM_STR = re.compile(r"^randomString\(\s*(\d+)\s*\)$")
_RANDOM_FROM = re.compile(r"^randomFrom\((.+)\)$")
_DATE_OFFSET = re.compile(r"^dateOffset\(\s*(-?\d+)\s*,\s*['\"]?(day|days|hour|hours|minute|minutes)['\"]?\s*\)$")

# matches any ${...} token (name or name(args))
_TOKEN = re.compile(r"\$\{([^}]+)\}")

# the set of names/prefixes we treat as generators (vs data columns / corr vars)
_GENERATOR_PREFIXES = ("uuid", "randomInt", "randomEmail", "randomString",
                       "timestamp", "sequential", "randomFrom", "vu", "iter",
                       "randomFullName", "randomFirstName", "randomLastName",
                       "randomCompanyName", "randomCatchPhrase", "randomCity",
                       "randomStreetAddress", "randomPhone", "randomBic",
                       "randomBankAccountBic", "randomZipCode", "randomState",
                       "dateOffset")


def is_generator(token: str) -> bool:
    """True if a ${token}'s inner text is one of our generators (not a column/var)."""
    t = token.strip()
    return any(t == p or t.startswith(p + "(") for p in _GENERATOR_PREFIXES)


def needs_uuid_import(model) -> bool:
    """Whether any body/path uses ${uuid} (so the script imports uuidv4)."""
    for sc in model.scenarios:
        for st in sc.steps:
            blob = st.path + (str(st.body) if st.body else "")
            for m in _TOKEN.findall(blob):
                if m.strip() == "uuid":
                    return True
    return False


def generator_js(token: str) -> str | None:
    """Return the k6 JS expression for a generator token, or None if not a generator."""
    t = token.strip()
    if t in _SIMPLE:
        return _SIMPLE[t]
    m = _RANDOM_INT.match(t)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return f"(Math.floor(Math.random() * ({hi} - {lo} + 1)) + {lo})"
    m = _RANDOM_STR.match(t)
    if m:
        n = int(m.group(1))
        return f"Math.random().toString(36).slice(2).padEnd({n},'0').slice(0,{n})"
    m = _DATE_OFFSET.match(t)
    if m:
        n = int(m.group(1)); unit = m.group(2).rstrip("s")
        ms = {"day": 86400000, "hour": 3600000, "minute": 60000}[unit]
        return f"new Date(Date.now() + ({n} * {ms})).toISOString()"
    m = _RANDOM_FROM.match(t)
    if m:
        # split args on commas, trim, quote the ones that aren't numeric
        parts = [p.strip() for p in m.group(1).split(",")]
        items = []
        for p in parts:
            if re.fullmatch(r"-?\d+(\.\d+)?", p):
                items.append(p)
            else:
                items.append('"' + p.strip('"\'') + '"')
        arr = "[" + ", ".join(items) + "]"
        return f"{arr}[Math.floor(Math.random() * {len(items)})]"
    return None


# The UUID import line (k6 jslib) — included only when ${uuid} is used.
UUID_IMPORT = "import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';"


# ---- self-contained realistic-data helpers (no external faker needed) ----
# Emitted into the script only when a realistic generator is used, so any standard
# k6 binary can run it (no custom extension, no fragile CDN dependency).

_FAKER_NAMES = ("uuid",)  # placeholder; real detection below

_REALISTIC_TOKENS = (
    "randomFullName", "randomFirstName", "randomLastName", "randomCompanyName",
    "randomCatchPhrase", "randomCity", "randomStreetAddress", "randomPhone",
    "randomBic", "randomBankAccountBic", "randomZipCode", "randomState",
)


def needs_faker(model) -> bool:
    """True if any body/path uses a realistic generator (so we emit the helpers)."""
    for sc in model.scenarios:
        for st in sc.steps:
            blob = st.path + (str(st.body) if st.body else "")
            for m in _TOKEN.findall(blob):
                base = m.strip().split("(")[0]
                if base in _REALISTIC_TOKENS:
                    return True
    return False


FAKER_HELPERS = r"""
// --- lightweight fake-data helpers (self-contained; no external deps) ---
const _FN = ['James','Mary','John','Patricia','Robert','Jennifer','Michael','Linda','David','Elizabeth','Maria','Jose','Ana','Luis','Chen','Wei','Omar','Sara','Raj','Priya'];
const _LN = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Rodriguez','Martinez','Lee','Kim','Patel','Nguyen','Khan','Silva','Wang','Ali','Haddad','Costa'];
const _CO = ['Acme','Globex','Initech','Umbrella','Soylent','Stark','Wayne','Wonka','Hooli','Vandelay','Cyberdyne','Tyrell','Massive Dynamic','Pied Piper'];
const _CP = ['Streamlined zero-tolerance core','Optimized reciprocal pipeline','Robust tertiary synergy','Scalable realtime interface','Proactive incremental matrix','User-centric agile hub'];
const _CI = ['Phoenix','Austin','Denver','Seattle','Miami','Boston','Chicago','Dallas','Portland','Atlanta'];
const _ST = ['AZ','TX','CO','WA','FL','MA','IL','CA','OR','GA'];
const _STR = ['Main St','Oak Ave','Pine Rd','Maple Dr','Cedar Ln','Elm St','Buckeye Rd','Beale Rd','Bristol Pkwy'];
function _pick(a){ return a[Math.floor(Math.random()*a.length)]; }
function fakeFirstName(){ return _pick(_FN); }
function fakeLastName(){ return _pick(_LN); }
function fakeName(){ return _pick(_FN)+' '+_pick(_LN); }
function fakeCompany(){ return _pick(_CO)+' '+_pick(['Inc','LLC','Corp','Group','Co']); }
function fakeCatchPhrase(){ return _pick(_CP); }
function fakeCity(){ return _pick(_CI); }
function fakeState(){ return _pick(_ST); }
function fakeStreet(){ return (Math.floor(Math.random()*9900)+100)+' '+_pick(_STR); }
function fakeZip(){ return String(Math.floor(Math.random()*90000)+10000); }
function fakePhone(){ return '('+(Math.floor(Math.random()*800)+200)+') '+(Math.floor(Math.random()*800)+200)+'-'+String(Math.floor(Math.random()*10000)).padStart(4,'0'); }
function fakeBic(){ let s=''; const L='ABCDEFGHIJKLMNOPQRSTUVWXYZ'; for(let i=0;i<8;i++) s+=L[Math.floor(Math.random()*26)]; return s; }
"""
