"""Conversational chat — draft logic, the LangGraph flow, persistence, guardrails, API.

Everything runs against a scripted fake provider and a temp database, so no network
or API key is needed.
"""

from __future__ import annotations

import importlib

import pytest

from perfagent.chat import (
    ChatService,
    ChatTurn,
    EmptyMessage,
    MessageTooLong,
    NotReady,
    ProviderUnavailable,
    SessionNotFound,
    TurnLimitReached,
    assess,
    merge_intent,
)
from perfagent.chat.prompts import build_turn_prompt
from perfagent.chat_intent import ChatEndpoint, ChatIntent
from perfagent.config import Settings
from perfagent.contracts.load_model import (
    LoadModel,
    LoadProfile,
    LoadProfileType,
    Scenario,
    Stage,
    Step,
)
from perfagent.guardrails import GuardedProvider

# ---------------------------------------------------------------- helpers ----


def _canned_model() -> LoadModel:
    return LoadModel(
        target_base_url="http://placeholder",
        scenarios=[Scenario(name="login", weight=1.0,
                            steps=[Step(name="login", method="POST", path="/login")])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=60, target_users=10)]),
    )


class ScriptedProvider:
    """Returns the queued ChatTurns in order; a queued Exception is raised instead.
    Any LoadModel request gets a canned plan."""

    name = "scripted"

    def __init__(self, turns=None):
        self.turns = list(turns or [])
        self.prompts: list[str] = []        # user prompts as the LLM would see them
        self.plan_calls = 0
        self.fail_plan = False

    def structured(self, *, response_model, system, user):
        self.prompts.append(user)
        if response_model is ChatTurn:
            item = self.turns.pop(0) if self.turns else ChatTurn(reply="ok")
            if isinstance(item, Exception):
                raise item
            return item
        self.plan_calls += 1
        if self.fail_plan:
            raise RuntimeError("planner down")
        return _canned_model()


def _settings(**over) -> Settings:
    base = {"chat_checkpoint_db": ":memory:"}
    base.update(over)
    return Settings(_env_file=None, **base)


def _make_engine(db_url):
    from sqlalchemy import create_engine

    from perfagent.db.models import Base
    eng = create_engine(db_url)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Point the app database at a temp file."""
    from perfagent.db import models as dbmodels

    dbmodels._engine = None
    eng = _make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(dbmodels, "get_engine", lambda *_a, **_k: eng)
    yield tmp_path
    eng.dispose()


def _service(provider, **settings_over) -> ChatService:
    return ChatService(lambda: provider, settings=_settings(**settings_over),
                       retry_delay_seconds=0)


LOGIN = ChatEndpoint(method="POST", path="/login", example_body={"user": "demo"})


# ------------------------------------------------------------ draft logic ----


def test_merge_keeps_what_the_model_did_not_restate():
    prev = ChatIntent(target_base_url="https://shop.test", goal="login test",
                      endpoints=[LOGIN], max_users=50, duration_seconds=120)
    merged = merge_intent(prev, ChatIntent(max_users=200))
    assert merged.target_base_url == "https://shop.test"
    assert merged.goal == "login test"
    assert [e.path for e in merged.endpoints] == ["/login"]
    assert merged.max_users == 200
    assert merged.duration_seconds == 120


def test_merge_replaces_endpoint_list_so_removal_works():
    prev = ChatIntent(endpoints=[LOGIN, ChatEndpoint(path="/checkout")])
    merged = merge_intent(prev, ChatIntent(endpoints=[LOGIN]))
    assert [e.path for e in merged.endpoints] == ["/login"]


def test_merge_normalises_paths_and_drops_duplicates():
    merged = merge_intent(ChatIntent(), ChatIntent(endpoints=[
        ChatEndpoint(path="products"),
        ChatEndpoint(path="https://shop.test/products"),
        ChatEndpoint(method="POST", path="/products"),
    ]))
    assert [(e.method.value, e.path) for e in merged.endpoints] == [
        ("GET", "/products"), ("POST", "/products")]


def test_merge_ignores_a_target_that_is_not_a_url():
    prev = ChatIntent(target_base_url="https://shop.test")
    assert merge_intent(prev, ChatIntent(target_base_url="staging")).target_base_url \
        == "https://shop.test"
    assert merge_intent(ChatIntent(), ChatIntent(target_base_url="staging")).target_base_url == ""


def test_assess_is_decided_by_code():
    r = assess(ChatIntent())
    assert r.missing == ["target", "endpoints"] and not r.ready
    r = assess(ChatIntent(target_base_url="https://shop.test", endpoints=[LOGIN]))
    assert r.ready and r.assumed == {"max_users": True, "duration_seconds": True}
    r = assess(ChatIntent(target_base_url="https://shop.test", endpoints=[LOGIN],
                          max_users=10, duration_seconds=30))
    assert r.assumed == {"max_users": False, "duration_seconds": False}


def test_turn_prompt_carries_draft_history_and_latest_message():
    p = build_turn_prompt(
        intent=ChatIntent(target_base_url="https://shop.test"),
        missing=["endpoints"],
        history=[{"role": "user", "content": "hello"},
                 {"role": "assistant", "content": "which endpoints?"}],
        message="POST /login",
        collection_text="x" * 20000,
    )
    assert "https://shop.test" in p and "at least one endpoint" in p
    assert "assistant: which endpoints?" in p and "POST /login" in p
    assert p.count("x") <= 8000 + 50        # the pasted collection is bounded


# ------------------------------------------------------------- graph flow ----


def test_conversation_collects_then_builds(temp_db):
    provider = ScriptedProvider([
        ChatTurn(reply="Which URL?", intent=ChatIntent(goal="login test", endpoints=[LOGIN])),
        ChatTurn(reply="Got it.", intent=ChatIntent(target_base_url="https://shop.test",
                                                    max_users=50)),
    ])
    svc = _service(provider)

    v = svc.start("load test the login endpoint")
    assert v["status"] == "collecting" and v["missing"] == ["target"] and not v["ready"]
    assert [m["role"] for m in v["messages"]] == ["user", "assistant"]
    assert v["plan"] is None

    v = svc.send(v["session_id"], "https://shop.test with 50 users")
    assert v["status"] == "ready" and v["ready"] and v["missing"] == []
    assert v["draft"]["max_users"] == 50
    assert v["draft"]["duration_seconds"] == 60 and v["draft"]["assumed"]["duration_seconds"]
    assert v["draft"]["endpoints"][0]["path"] == "/login"     # carried over from turn 1
    assert provider.plan_calls == 0                            # nothing built yet

    v = svc.build(v["session_id"])
    assert v["status"] == "planned" and v["plan_current"]
    plan = v["plan"]
    assert plan["load_model"]["target_base_url"] == "https://shop.test"   # forced by code
    assert plan["plan_id"] and "evaluation" in plan and "guardrail" in plan
    assert v["messages"][-1]["kind"] == "plan"

    # the plan is saved like any other, ready for the Review step
    from perfagent.db import PlanRow, get_session
    with get_session() as s:
        assert s.get(PlanRow, plan["plan_id"]) is not None


def test_go_ahead_in_chat_builds_only_when_ready(temp_db):
    provider = ScriptedProvider([
        # asks to build, but the target is missing -> must NOT build
        ChatTurn(reply="Need the URL first.", intent=ChatIntent(endpoints=[LOGIN]),
                 wants_plan=True),
        ChatTurn(reply="Building.", intent=ChatIntent(target_base_url="https://shop.test"),
                 wants_plan=True),
    ])
    svc = _service(provider)
    v = svc.start("test login, go ahead")
    assert v["status"] == "collecting" and provider.plan_calls == 0
    v = svc.send(v["session_id"], "https://shop.test — go ahead")
    assert v["status"] == "planned" and provider.plan_calls == 1


def test_build_refused_while_essentials_missing(temp_db):
    svc = _service(ScriptedProvider([ChatTurn(reply="?", intent=ChatIntent())]))
    v = svc.start("hi")
    with pytest.raises(NotReady) as e:
        svc.build(v["session_id"])
    assert len(e.value.prompts) == 2


def test_changing_the_draft_marks_the_plan_stale(temp_db):
    provider = ScriptedProvider([
        ChatTurn(reply="ok", intent=ChatIntent(target_base_url="https://shop.test",
                                               endpoints=[LOGIN])),
        ChatTurn(reply="200 users now.", intent=ChatIntent(max_users=200)),
        ChatTurn(reply="Nothing changed."),
    ])
    svc = _service(provider)
    sid = svc.start("login at https://shop.test")["session_id"]
    assert svc.build(sid)["status"] == "planned"
    v = svc.send(sid, "make it 200 users")
    assert v["status"] == "ready" and not v["plan_current"] and v["plan"] is not None
    v = svc.build(sid)
    assert v["status"] == "planned" and provider.plan_calls == 2
    # a turn that changes nothing leaves the plan current
    assert svc.send(sid, "thanks")["plan_current"]


def test_llm_failure_is_recovered_inside_the_conversation(temp_db):
    provider = ScriptedProvider([
        RuntimeError("boom"), RuntimeError("boom again"),     # both attempts of turn 1
        ChatTurn(reply="ok", intent=ChatIntent(target_base_url="https://shop.test",
                                               endpoints=[LOGIN])),
    ])
    svc = _service(provider)
    v = svc.start("login at https://shop.test")
    assert v["messages"][-1]["kind"] == "error" and "boom" in v["error"]
    assert v["status"] == "collecting"
    v = svc.send(v["session_id"], "login at https://shop.test")       # just try again
    assert v["status"] == "ready" and v["error"] == ""


def test_transient_llm_failure_is_retried_once(temp_db):
    provider = ScriptedProvider([
        RuntimeError("blip"),
        ChatTurn(reply="ok", intent=ChatIntent(target_base_url="https://shop.test",
                                               endpoints=[LOGIN])),
    ])
    v = _service(provider).start("login at https://shop.test")
    assert v["status"] == "ready" and v["error"] == ""


def test_plan_failure_keeps_the_draft(temp_db):
    provider = ScriptedProvider([
        ChatTurn(reply="ok", intent=ChatIntent(target_base_url="https://shop.test",
                                               endpoints=[LOGIN])),
    ])
    svc = _service(provider)
    sid = svc.start("login at https://shop.test")["session_id"]
    provider.fail_plan = True
    v = svc.build(sid)
    assert v["status"] == "ready" and v["plan"] is None
    assert v["messages"][-1]["kind"] == "error"
    provider.fail_plan = False
    assert svc.build(sid)["status"] == "planned"


def test_limits(temp_db):
    svc = _service(ScriptedProvider(), chat_max_turns=2, chat_max_message_chars=20)
    with pytest.raises(EmptyMessage):
        svc.start("   ")
    with pytest.raises(MessageTooLong):
        svc.start("x" * 21)
    sid = svc.start("one")["session_id"]
    assert svc.send(sid, "two")["turns_left"] == 0
    with pytest.raises(TurnLimitReached):
        svc.send(sid, "three")
    with pytest.raises(SessionNotFound):
        svc.get("nope")
    with pytest.raises(SessionNotFound):
        svc.send("nope", "hello")


def test_missing_provider_fails_fast_without_creating_a_session(temp_db):
    def no_key():
        raise ValueError("OPENAI_API_KEY is not set (see .env).")

    svc = ChatService(no_key, settings=_settings())
    with pytest.raises(ProviderUnavailable):
        svc.start("hello")
    assert svc.list() == []


def test_history_window_bounds_the_prompt(temp_db):
    provider = ScriptedProvider()
    svc = _service(provider, chat_history_window=2)
    sid = svc.start("message-one")["session_id"]
    svc.send(sid, "message-two")
    svc.send(sid, "message-three")
    last = provider.prompts[-1]
    assert "message-three" in last and "message-two" in last
    assert "message-one" not in last


# ------------------------------------------------------------- guardrails ----


def test_secrets_never_reach_the_llm_or_the_checkpoint(temp_db):
    inner = ScriptedProvider([
        ChatTurn(reply="ok", intent=ChatIntent(target_base_url="http://<HOST_1>",
                                               endpoints=[LOGIN])),
    ])
    svc = ChatService(lambda: GuardedProvider(inner), settings=_settings(),
                      retry_delay_seconds=0)
    v = svc.start("login at http://10.0.0.5:8000 with password: hunter2 for bob@corp.com",
                  collection_text='{"token": "abcdefghijklmnop"}')

    sent = "\n".join(inner.prompts)
    for secret in ("hunter2", "bob@corp.com", "abcdefghijklmnop", "10.0.0.5"):
        assert secret not in sent
    stored = repr(v["messages"])
    assert "hunter2" not in stored and "bob@corp.com" not in stored
    # the host stays readable for the user and is restored into the draft
    assert "10.0.0.5:8000" in v["messages"][0]["content"]
    assert v["draft"]["target_base_url"] == "http://10.0.0.5:8000"
    assert v["guardrail"]["total"] >= 3
    assert v["messages"][1]["kind"] == "attachment"


def test_masked_body_values_are_flagged(temp_db):
    provider = ScriptedProvider([ChatTurn(reply="ok", intent=ChatIntent(
        target_base_url="https://shop.test",
        endpoints=[ChatEndpoint(method="POST", path="/login",
                                example_body={"password": "<FIELD_REDACTED>"})]))])
    v = _service(provider).start("login with password: hunter2")
    assert v["draft"]["secrets_masked"] is True


# ------------------------------------------------------------ persistence ----


def test_conversation_survives_a_restart(temp_db):
    db = str(temp_db / "chat.db")
    turns = [ChatTurn(reply="Which URL?", intent=ChatIntent(endpoints=[LOGIN])),
             ChatTurn(reply="ok", intent=ChatIntent(target_base_url="https://shop.test"))]
    provider = ScriptedProvider(turns)

    first = _service(provider, chat_checkpoint_db=db)
    sid = first.start("test login")["session_id"]
    first.close()                                    # "restart"

    second = _service(provider, chat_checkpoint_db=db)
    try:
        v = second.get(sid)
        assert v["status"] == "collecting" and len(v["messages"]) == 2
        v = second.send(sid, "https://shop.test")
        assert v["status"] == "ready" and v["draft"]["endpoints"][0]["path"] == "/login"
        assert [s["session_id"] for s in second.list()] == [sid]
        second.delete(sid)
        with pytest.raises(SessionNotFound):
            second.get(sid)
        assert second.list() == []
    finally:
        second.close()


# -------------------------------------------------------------------- API ----


@pytest.fixture()
def client(temp_db, monkeypatch):
    from perfagent import config
    from perfagent.api import app as appmod
    from perfagent.api import chat_routes

    importlib.reload(appmod)
    chat_routes.reset_service()
    settings = _settings()
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(chat_routes, "get_settings", lambda: settings)
    provider = ScriptedProvider([
        ChatTurn(reply="Which URL?", intent=ChatIntent(endpoints=[LOGIN])),
        ChatTurn(reply="ok", intent=ChatIntent(target_base_url="https://shop.test")),
    ])
    monkeypatch.setattr(chat_routes, "_provider", lambda: provider)
    monkeypatch.setattr(
        chat_routes, "get_service",
        _cached(lambda: ChatService(lambda: chat_routes._provider(), settings=settings,
                                    retry_delay_seconds=0)))

    from fastapi.testclient import TestClient
    c = TestClient(appmod.app)
    c.settings = settings
    yield c
    chat_routes.reset_service()


def _cached(factory):
    box = {}

    def get():
        if "svc" not in box:
            box["svc"] = factory()
        return box["svc"]
    return get


def test_api_full_flow(client):
    assert client.get("/api/chat/config").json()["enabled"] is True

    r = client.post("/api/chat/sessions", json={"message": "test login"})
    assert r.status_code == 200
    v = r.json()
    sid = v["session_id"]
    assert v["status"] == "collecting"

    assert client.post(f"/api/chat/sessions/{sid}/build").status_code == 409

    v = client.post(f"/api/chat/sessions/{sid}/messages",
                    json={"message": "https://shop.test"}).json()
    assert v["status"] == "ready"

    v = client.post(f"/api/chat/sessions/{sid}/build").json()
    assert v["status"] == "planned"
    plan_id = v["plan"]["plan_id"]
    # the plan flows into the existing pipeline unchanged
    assert client.get(f"/api/plans/{plan_id}").status_code == 200
    g = client.post(f"/api/plan/{plan_id}/generate", json={"tool": "k6"})
    assert g.status_code == 200 and "/login" in g.json()["content"]

    assert client.get(f"/api/chat/sessions/{sid}").json()["plan"]["plan_id"] == plan_id
    sessions = client.get("/api/chat/sessions").json()["sessions"]
    assert sessions[0]["session_id"] == sid and sessions[0]["plan_id"] == plan_id

    assert client.delete(f"/api/chat/sessions/{sid}").status_code == 200
    assert client.get(f"/api/chat/sessions/{sid}").status_code == 404
    actions = [e["action"] for e in client.get("/api/audit").json()["events"]]
    for a in ("chat.started", "chat.turn", "plan.created", "chat.deleted"):
        assert a in actions


def test_api_errors(client):
    assert client.post("/api/chat/sessions", json={"message": "  "}).status_code == 400
    assert client.get("/api/chat/sessions/nope").status_code == 404
    assert client.post("/api/chat/sessions/nope/messages",
                       json={"message": "hi"}).status_code == 404
    assert client.post("/api/chat/sessions/nope/build").status_code == 404
    assert client.delete("/api/chat/sessions/nope").status_code == 404


def test_api_can_be_switched_off(client):
    client.settings.chat_conversation_enabled = False
    assert client.get("/api/chat/config").json()["enabled"] is False
    assert client.post("/api/chat/sessions", json={"message": "hi"}).status_code == 404
    assert client.get("/api/chat/sessions").status_code == 404


def test_single_shot_chat_plan_is_untouched(client):
    """The old one-shot endpoint still exists alongside the conversation."""
    paths = client.app.openapi()["paths"]
    assert "/api/chat-plan" in paths and "/api/chat/sessions" in paths
