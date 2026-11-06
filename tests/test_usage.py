"""Tests for token usage tracking."""

from __future__ import annotations

from perfagent.usage import Usage, extract_usage


def test_usage_total_and_cost():
    u = Usage(prompt_tokens=1000, completion_tokens=500, model="gpt-4o")
    assert u.total_tokens == 1500
    assert u.cost_usd() > 0
    s = u.summary()
    assert s["total_tokens"] == 1500 and s["cost_usd"] > 0


def test_extract_openai_style():
    class _U: prompt_tokens = 800; completion_tokens = 200
    class _R: usage = _U()
    u = extract_usage(_R(), "gpt-4o-mini")
    assert u.prompt_tokens == 800 and u.completion_tokens == 200


def test_extract_anthropic_style():
    class _U: input_tokens = 500; output_tokens = 150
    class _R: usage = _U()
    u = extract_usage(_R(), "claude-3-5-sonnet")
    assert u.prompt_tokens == 500 and u.completion_tokens == 150


def test_extract_no_usage_is_safe():
    class _Empty: pass
    u = extract_usage(_Empty(), "gpt-4o")
    assert u.total_tokens == 0


def test_unknown_model_uses_default_price():
    u = Usage(prompt_tokens=1_000_000, completion_tokens=0, model="some-unknown-model")
    assert u.cost_usd() > 0   # falls back to default price, not zero
