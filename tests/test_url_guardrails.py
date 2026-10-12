"""Additional guardrail tests for URL host masking and query-string secrets.

Append these to tests/test_guardrails.py (or keep as a separate test file).
"""

from __future__ import annotations

from perfagent.guardrails import redact, restore


def test_url_host_masked_path_kept():
    r = redact("call https://api.stripe.com/v1/charges now")
    assert "api.stripe.com" not in r.text      # host masked
    assert "/v1/charges" in r.text             # path kept (AI needs it)
    assert "<HOST_1>" in r.text
    # host is reversible -> restored in reports
    assert "api.stripe.com" in restore(r.text, r.mapping)


def test_url_query_secret_stripped_one_way():
    r = redact("GET https://api.acme.com/pay?token=SECRET123&amount=50")
    assert "SECRET123" not in r.text           # secret gone
    assert "amount=50" in r.text               # non-secret query param kept
    assert "api.acme.com" not in r.text        # host masked
    # query secret is one-way: never restored
    assert "SECRET123" not in restore(r.text, r.mapping)


def test_url_multiple_query_secrets():
    r = redact("https://x.com/a?api_key=abc123&sig=deadbeef&page=2")
    assert "abc123" not in r.text
    assert "deadbeef" not in r.text
    assert "page=2" in r.text


def test_internal_host_in_url_masked():
    r = redact("https://payments.internal/checkout")
    assert "payments.internal" not in r.text
    assert restore(r.text, r.mapping).count("payments.internal") == 1


def test_same_host_stable_placeholder_across_urls():
    r = redact("https://api.acme.com/a then https://api.acme.com/b")
    # one host -> one placeholder, used twice
    hosts = [k for k in r.mapping if k.startswith("<HOST_")]
    assert len(hosts) == 1
    assert restore(r.text, r.mapping).count("api.acme.com") == 2


def test_public_host_with_port():
    r = redact("http://127.0.0.1:8000/products")
    assert "127.0.0.1:8000" not in r.text
    assert "/products" in r.text