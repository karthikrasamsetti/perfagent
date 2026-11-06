"""Tests for the AI dynamize schema (add generators to a body)."""

from __future__ import annotations

from perfagent.dynamize import (
    DynamizedBody,
    build_dynamize_user_prompt,
)


def test_dynamized_body_preserves_structure():
    out = DynamizedBody(
        body={
            "ServiceCode": "GRND",
            "DeliverTo": {"Contact": "${randomFullName}", "Email": "${randomEmail}"},
            "Pieces": [{"Weight": 3120, "Reference": "${randomBic}"}],
        },
        changed_fields=["DeliverTo.Contact", "DeliverTo.Email", "Pieces[0].Reference"],
        notes="Names/email/reference made dynamic; weight/codes kept.",
    )
    # fixed values preserved
    assert out.body["ServiceCode"] == "GRND"
    assert out.body["Pieces"][0]["Weight"] == 3120
    # dynamic fields assigned
    assert out.body["DeliverTo"]["Email"] == "${randomEmail}"
    assert out.body["DeliverTo"]["Contact"] == "${randomFullName}"
    assert len(out.changed_fields) == 3


def test_dynamize_prompt_includes_body():
    p = build_dynamize_user_prompt('{"Email": "a@b.com"}')
    assert "Email" in p
    assert "dynamic" in p.lower()


def test_empty_changed_fields_ok():
    out = DynamizedBody(body={"x": 1})
    assert out.changed_fields == []
    assert out.notes == ""


# ---- data-file column awareness ----

def test_prompt_lists_data_columns():
    from perfagent.dynamize import build_dynamize_user_prompt
    p = build_dynamize_user_prompt('{"CustomerBranch":"X"}', ["branch", "account"])
    assert "branch, account" in p
    assert "data-file column" in p.lower()


def test_prompt_without_columns_has_no_column_section():
    from perfagent.dynamize import build_dynamize_user_prompt
    p = build_dynamize_user_prompt('{"x":1}')
    assert "Available data-file columns" not in p


def test_system_prompt_prefers_columns_for_real_values():
    from perfagent.dynamize import DYNAMIZE_SYSTEM_PROMPT
    assert "DATA-FILE COLUMNS" in DYNAMIZE_SYSTEM_PROMPT
    assert "INSTEAD of a random generator" in DYNAMIZE_SYSTEM_PROMPT


def test_three_sources_in_dynamized_body():
    from perfagent.dynamize import DynamizedBody
    out = DynamizedBody(body={
        "CustomerBranch": "${branch}",       # data-file column (real value)
        "OrderId": "${uuid}",                # generator (unique)
        "Weight": 3120,                      # fixed
    })
    assert out.body["CustomerBranch"] == "${branch}"
    assert out.body["OrderId"] == "${uuid}"
    assert out.body["Weight"] == 3120
