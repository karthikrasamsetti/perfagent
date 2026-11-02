"""Comprehensive guardrail verification — run this BEFORE testing real endpoints.

It feeds realistic sensitive data through the redaction + output-scrub layers and
asserts that nothing sensitive survives into what the LLM would receive. No API key
needed (it uses a fake capturing provider), no network calls.

    uv run python verify_guardrails.py
"""

from __future__ import annotations

from pydantic import BaseModel

from perfagent.guardrails import GuardedProvider, redact, restore


GREEN = "\033[92m"; RED = "\033[91m"; DIM = "\033[2m"; END = "\033[0m"


def check(name: str, condition: bool, detail: str = "") -> bool:
    mark = f"{GREEN}PASS{END}" if condition else f"{RED}FAIL{END}"
    print(f"  [{mark}] {name}")
    if detail:
        print(f"        {DIM}{detail}{END}")
    return condition


# ---- 1. INPUT redaction: every category ----
print("\n=== 1. INPUT redaction (what the LLM must NEVER see) ===")
cases = {
    "email": ("Contact jane.doe@acme.com", "jane.doe@acme.com"),
    "password field": ('{"password": "Hunter2!"}', "Hunter2!"),
    "inline secret": ("password=SuperSecret1", "SuperSecret1"),
    "JWT": ("Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcDEF123456", "eyJhbGci"),
    "API key": ("key sk-abcdef1234567890ABCDEF", "sk-abcdef1234567890ABCDEF"),
    "credit card": ("card 4242 4242 4242 4242", "4242 4242 4242 4242"),
    "SSN": ("ssn 123-45-6789", "123-45-6789"),
    "URL query secret": ("GET https://api.acme.com/p?token=SEKRET123", "SEKRET123"),
    "private IP": ("host 10.0.4.21", "10.0.4.21"),
}
all_ok = True
for name, (text, secret) in cases.items():
    out = redact(text).text
    ok = secret not in out
    all_ok &= check(name, ok, f"{text!r}  ->  {out!r}")

# ---- 2. URL host masked (reversible) but path kept ----
print("\n=== 2. URL handling (host masked, path kept, restorable) ===")
r = redact("call https://api.acme.com/v1/login now")
all_ok &= check("host masked", "api.acme.com" not in r.text, r.text)
all_ok &= check("path kept", "/v1/login" in r.text)
all_ok &= check("host restorable in reports", "api.acme.com" in restore(r.text, r.mapping))

# ---- 3. ${placeholder} preserved (not treated as a secret) ----
print("\n=== 3. Template placeholders preserved ===")
r = redact('{"username":"${username}","password":"${password}"}')
all_ok &= check("${username} survives", "${username}" in r.text)
all_ok &= check("${password} survives", "${password}" in r.text, r.text)

# ---- 4. GuardedProvider: the LLM only ever receives redacted text ----
print("\n=== 4. End-to-end: GuardedProvider never sends secrets ===")

class _Plan(BaseModel):
    note: str

class _Spy:
    name = "spy"
    def __init__(self): self.seen_system = None; self.seen_user = None
    def structured(self, *, response_model, system, user):
        self.seen_system = system; self.seen_user = user
        return _Plan(note="ok")

spy = _Spy()
guard = GuardedProvider(spy)
guard.structured(
    response_model=_Plan,
    system="You are a planner.",
    user=('Test POST /login body {"email":"admin@corp.com","password":"secret123"} '
          'at https://api.internal/login?token=abc123'),
)
sent = (spy.seen_system or "") + "\n" + (spy.seen_user or "")
for secret in ["admin@corp.com", "secret123", "abc123", "api.internal"]:
    all_ok &= check(f"'{secret}' not sent to LLM", secret not in sent)
print(f"        {DIM}LLM actually received: {spy.seen_user}{END}")
print(f"        {DIM}redaction counts: {guard.last_redaction_counts}{END}")

# ---- 5. OUTPUT scrubbing: a leaked secret in the model's reply is removed ----
print("\n=== 5. OUTPUT scrubbing (model tries to leak a secret) ===")

class _Report(BaseModel):
    summary: str

class _Leaky:
    name = "leaky"
    def structured(self, *, response_model, system, user):
        return _Report(summary="All good. Debug key sk-LEAKED1234567890ABCDEF fyi.")

out = GuardedProvider(_Leaky()).structured(response_model=_Report, system="s", user="u")
all_ok &= check("leaked key scrubbed from output", "sk-LEAKED1234567890ABCDEF" not in out.summary,
                out.summary)

# ---- verdict ----
print()
if all_ok:
    print(f"{GREEN}ALL GUARDRAILS VERIFIED — safe to proceed to real endpoints.{END}\n")
else:
    print(f"{RED}SOME GUARDRAILS FAILED — do NOT use real/sensitive data until fixed.{END}\n")
    raise SystemExit(1)
