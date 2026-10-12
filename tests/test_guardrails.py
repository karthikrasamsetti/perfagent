"""Tests for the guardrails — proving sensitive data never reaches the LLM."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from perfagent.guardrails import GuardedProvider, redact, restore
from perfagent.guardrails.redaction import redact_text

T = TypeVar("T", bound=BaseModel)


# ---- redaction unit tests ----

def test_email_is_redacted_one_way():
    r = redact("contact me at jane.doe@example.com please")
    assert "jane.doe@example.com" not in r.text
    assert "<EMAIL_REDACTED>" in r.text
    assert r.mapping == {}  # secrets are never reversible


def test_jwt_is_redacted():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcDEF123456"
    r = redact(f"Authorization: Bearer {jwt}")
    assert jwt not in r.text
    assert "REDACTED" in r.text


def test_api_key_is_redacted():
    r = redact("key is sk-abcdef1234567890ABCDEF here")
    assert "sk-abcdefit1234567890ABCDEF" not in r.text
    assert "sk-abcdef1234567890ABCDEF" not in r.text


def test_credit_card_redacted_only_if_luhn_valid():
    # 4242 4242 4242 4242 is a valid Luhn test card -> redacted
    r = redact("card 4242 4242 4242 4242 on file")
    assert "4242 4242 4242 4242" not in r.text
    # a Luhn-invalid 16-digit group -> left alone (not a real card)
    r2 = redact("id 1234 5678 9012 3456 x")
    assert "1234 5678 9012 3456" in r2.text


def test_ssn_redacted():
    r = redact("ssn 123-45-6789 on record")
    assert "123-45-6789" not in r.text


def test_secret_field_by_key_name():
    obj = {"user": "demo", "password": "hunter2", "token": "abc123"}
    r = redact(obj)
    assert r.text["password"] == "<FIELD_REDACTED>"
    assert r.text["token"] == "<FIELD_REDACTED>"
    assert r.text["user"] == "demo"  # non-secret field kept


def test_internal_host_is_reversible():
    r = redact("call https://payments.internal/checkout now")
    assert "payments.internal" not in r.text
    assert r.mapping  # reversible mapping recorded
    # restoring brings it back
    restored = restore(r.text, r.mapping)
    assert "payments.internal" in restored


def test_private_ip_reversible():
    r = redact("host at 10.0.3.14 responds")
    assert "10.0.3.14" not in r.text
    assert restore(r.text, r.mapping).count("10.0.3.14") == 1


def test_same_identifier_gets_stable_placeholder():
    r = redact("a.internal talks to a.internal and b.internal")
    # a.internal should map to ONE placeholder used twice
    placeholders = [p for p in r.mapping]
    assert len(placeholders) == 2  # a.internal, b.internal
    restored = restore(r.text, r.mapping)
    assert restored.count("a.internal") == 2


def test_nested_json_redaction():
    obj = {"steps": [{"body": {"email": "x@y.com", "password": "p"}}]}
    r = redact(obj)
    body = r.text["steps"][0]["body"]
    assert "x@y.com" not in str(body)
    assert body["password"] == "<FIELD_REDACTED>"


# ---- guarded provider integration ----

class _CapturingProvider:
    """A fake provider that records exactly what it was sent."""
    name = "capture"

    def __init__(self, return_model):
        self._return = return_model
        self.seen_system = None
        self.seen_user = None

    def structured(self, *, response_model, system, user):
        self.seen_system = system
        self.seen_user = user
        return self._return


class _Plan(BaseModel):
    note: str


def test_guarded_provider_never_sends_secrets():
    inner = _CapturingProvider(_Plan(note="ok"))
    guard = GuardedProvider(inner)
    guard.structured(
        response_model=_Plan,
        system="You are a planner.",
        user="Test endpoint /login with body email=admin@corp.com password=secret123 "
             "against https://api.internal/login",
    )
    # the raw secrets must NOT appear in what the inner provider received
    assert "admin@corp.com" not in inner.seen_user
    assert "secret123" not in inner.seen_user
    assert "api.internal" not in inner.seen_user  # redacted (reversible) before sending
    # telemetry recorded counts
    assert guard.last_redaction_counts


def test_guarded_provider_restores_identifiers_in_output():
    # the model echoes back the placeholder; guard should restore the real host
    inner = _CapturingProvider(None)

    class Echo(BaseModel):
        text: str

    # figure out the placeholder the redactor will use for the host
    red = redact_text("https://api.internal/login", {}, {})
    placeholder = red.split("https://")[1].split("/")[0] if "<" in red else None

    # build a provider that returns the placeholder in its output
    inner._return = Echo(text=f"The service {placeholder} handled all requests.")
    guard = GuardedProvider(inner, restore_identifiers=True)
    out = guard.structured(
        response_model=Echo,
        system="s",
        user="test https://api.internal/login",
    )
    # after restore, the real host name is back in the narrative
    assert "api.internal" in out.text


def test_guarded_provider_scrubs_leaked_output():
    # if the model output contains a secret-looking value, it must be scrubbed
    class Echo(BaseModel):
        text: str

    inner = _CapturingProvider(Echo(text="Here is a key sk-LEAKED1234567890ABCDEFG oops"))
    guard = GuardedProvider(inner)
    out = guard.structured(response_model=Echo, system="s", user="u")
    assert "sk-LEAKED1234567890ABCDEFG" not in out.text


def test_inline_secret_in_prose_and_json_text():
    # secret written inline as key=value in free text
    r1 = redact("login with password=Hunter2! now")
    assert "Hunter2!" not in r1.text
    # secret written as quoted JSON key inside a text prompt
    r2 = redact('body: {"password": "Hunter2!", "user": "demo"}')
    assert "Hunter2!" not in r2.text
    assert "demo" in r2.text  # non-secret preserved