"""Regression tests: ${field} placeholders are not treated as secrets.

Append these to tests/test_guardrails.py (or keep as a separate file). They ensure
data-file template placeholders survive redaction while real secrets are still masked.
"""

from __future__ import annotations

from perfagent.guardrails import redact


def test_placeholder_in_inline_text_survives():
    r = redact('body {"username":"${username}","password":"${password}"}')
    assert "${username}" in r.text
    assert "${password}" in r.text          # placeholder, not a real secret


def test_placeholder_as_dict_value_survives():
    r = redact({"username": "${username}", "password": "${password}"})
    assert r.text["username"] == "${username}"
    assert r.text["password"] == "${password}"   # kept despite secret-looking key


def test_real_secret_still_redacted_alongside_placeholder():
    r = redact({"username": "${username}", "password": "Hunter2!"})
    assert r.text["username"] == "${username}"
    assert r.text["password"] == "<FIELD_REDACTED>"   # real value still masked


def test_real_inline_secret_still_redacted():
    r = redact("password=Hunter2!")
    assert "Hunter2" not in r.text


def test_email_and_host_still_handled_with_placeholders_present():
    r = redact('login ${username} at a@b.com via https://api.acme.com/x')
    assert "${username}" in r.text
    assert "a@b.com" not in r.text
    assert "api.acme.com" not in r.text