"""Tests for chat-to-plan intent extraction schema."""

from __future__ import annotations

from perfagent.chat_intent import (
    ChatEndpoint,
    ChatIntent,
    build_chat_user_prompt,
)
from perfagent.contracts.load_model import HttpMethod, LoadProfileType


def test_intent_captures_generators_in_bodies():
    intent = ChatIntent(
        target_base_url="https://staging.shop.com",
        goal="Load test signup",
        max_users=100, duration_seconds=120,
        endpoints=[
            ChatEndpoint(method="POST", path="/signup",
                         example_body={"email": "${randomEmail}", "name": "demo"}),
            ChatEndpoint(method="POST", path="/checkout",
                         example_body={"order_id": "${uuid}", "qty": "${randomInt(1,5)}"}),
        ],
    )
    assert intent.endpoints[0].example_body["email"] == "${randomEmail}"
    assert intent.endpoints[1].example_body["order_id"] == "${uuid}"
    assert intent.max_users == 100


def test_intent_clarification_when_missing():
    intent = ChatIntent(goal="test my api",
                        needs_clarification=["What's the target URL?"])
    assert not intent.target_base_url
    assert intent.needs_clarification


def test_profile_type_default_ramp():
    intent = ChatIntent()
    assert intent.profile_type == LoadProfileType.RAMP


def test_build_chat_user_prompt_includes_message_and_collection():
    p = build_chat_user_prompt("stress test these", collection_text='{"item":[]}')
    assert "stress test these" in p
    assert "collection" in p.lower()


def test_build_chat_user_prompt_truncates_long_collection():
    big = "x" * 20000
    p = build_chat_user_prompt("test", collection_text=big)
    assert len(p) < 12000   # collection is bounded to ~8000 chars
