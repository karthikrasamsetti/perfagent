"""The API documentation cannot drift from the code.

Every endpoint must be documented in perfagent/api/docs.py (group, summary,
description, access level), and every documented endpoint must exist.
"""

from __future__ import annotations

import pytest

from perfagent import __version__
from perfagent.api import docs
from perfagent.api.app import app

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture(scope="module")
def schema() -> dict:
    return app.openapi()


def _operations(schema):
    for path, item in schema["paths"].items():
        for method, op in item.items():
            if method in HTTP_METHODS:
                yield method.upper(), path, op


def test_every_endpoint_is_documented_and_nothing_is_stale(schema):
    live = {(m, p) for m, p, _ in _operations(schema)}
    documented = set(docs.ENDPOINTS)
    assert live - documented == set(), "add these to perfagent/api/docs.py"
    assert documented - live == set(), "these are documented but no longer exist"


def test_each_endpoint_has_group_summary_description_and_access(schema):
    groups = {t["name"] for t in docs.TAGS}
    for method, path, op in _operations(schema):
        where = f"{method} {path}"
        assert len(op.get("tags", [])) == 1 and op["tags"][0] in groups, where
        assert op["tags"] != ["default"], where
        assert len(op.get("summary", "")) >= 8, where
        assert len(op.get("description", "")) >= 40, where
        assert op.get("x-access") in docs.ACCESS_LEVELS, where
        assert isinstance(op.get("x-uses-ai"), bool), where
        assert "Access level" in op["description"], where
        ok = op["responses"]["200"]["description"]
        assert ok and ok != "Successful Response", where


def test_groups_are_described_and_all_used(schema):
    used = {op["tags"][0] for _, _, op in _operations(schema)}
    declared = [t["name"] for t in schema["tags"]]
    assert declared == [t["name"] for t in docs.TAGS]
    assert used == set(declared)                      # no empty group, no unknown group
    assert all(len(t["description"]) > 20 for t in schema["tags"])


def test_summaries_are_unique(schema):
    seen: dict[str, str] = {}
    for method, path, op in _operations(schema):
        key = op["summary"].lower()
        assert key not in seen, f"{method} {path} repeats the summary of {seen.get(key)}"
        seen[key] = f"{method} {path}"


def test_access_levels_match_what_the_endpoint_does(schema):
    """Reads are GETs; anything that only reads must not be a write level, and the
    calls that touch the target or an outside system are marked as such."""
    ops = {(m, p): op for m, p, op in _operations(schema)}
    for (method, path), op in ops.items():
        if op["x-access"] == "read" and method == "DELETE":
            raise AssertionError(f"DELETE {path} cannot be 'read'")
    assert ops[("POST", "/api/scripts/{script_id}/run")]["x-access"] == "run"
    assert ops[("POST", "/api/preflight")]["x-access"] == "run"
    assert ops[("POST", "/api/runs/{run_id}/stop")]["x-access"] == "run"
    assert ops[("POST", "/api/scripts/{script_id}/export/git")]["x-access"] == "integrate"
    assert ops[("POST", "/api/jenkins/trigger")]["x-access"] == "integrate"
    assert ops[("GET", "/api/health")]["x-access"] == "read"
    # every DELETE and every plan/script-creating call changes stored data
    for key in [("DELETE", "/api/sla/{sla_id}"), ("POST", "/api/plan"),
                ("POST", "/api/plan/{plan_id}/generate"), ("POST", "/api/data")]:
        assert ops[key]["x-access"] == "write", key


def test_ai_endpoints_are_flagged(schema):
    ops = {(m, p): op for m, p, op in _operations(schema)}
    for key in [("POST", "/api/plan"), ("POST", "/api/dynamize"),
                ("POST", "/api/suggest-checks"), ("POST", "/api/chat/sessions"),
                ("POST", "/api/chat/sessions/{session_id}/messages")]:
        assert ops[key]["x-uses-ai"] is True and "Uses AI" in ops[key]["description"], key
    for key in [("POST", "/api/request-preview"), ("POST", "/api/load-profile"),
                ("POST", "/api/plan/{plan_id}/generate"), ("POST", "/api/preflight"),
                ("POST", "/api/scripts/{script_id}/run")]:
        assert ops[key]["x-uses-ai"] is False, key


def test_api_metadata(schema):
    assert schema["info"]["title"] == docs.API_TITLE
    assert schema["info"]["version"] == __version__ != "0.1.0"
    assert "Access levels" in schema["info"]["description"]
    assert "/" not in schema["paths"]                 # the UI page is not an API endpoint
