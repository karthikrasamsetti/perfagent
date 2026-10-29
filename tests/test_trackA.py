"""Tests for Track A polish: token field variants + YAML OpenAPI import."""

from __future__ import annotations

from perfagent.contracts.load_model import (
    Extract,
    LoadModel,
    LoadProfile,
    LoadProfileType,
    Scenario,
    Stage,
    Step,
)
from perfagent.importers import import_endpoints
from perfagent.planner import PlanRequest, draft_plan
from perfagent.planner.spec import EndpointSpec


class _Fake:
    name = "fake"

    def __init__(self, model):
        self._m = model

    def structured(self, *, response_model, system, user):
        return self._m


def _req():
    return PlanRequest(target_base_url="http://x:8001", max_users=3, duration_seconds=10,
                       endpoints=[EndpointSpec(method="POST", path="/login")])


def _auth_model(var):
    return LoadModel(
        target_base_url="http://wrong",
        scenarios=[Scenario(name="auth", steps=[
            Step(name="login", method="POST", path="/login",
                 extract=[Extract(var=var, source="json", path=var)]),
            Step(name="me", method="GET", path="/me"),
        ])],
        load_profile=LoadProfile(type=LoadProfileType.RAMP,
                                 stages=[Stage(duration_seconds=5, target_users=3)]),
    )


def test_access_token_variant_auto_header():
    plan = draft_plan(_req(), _Fake(_auth_model("access_token")))
    assert plan.load_model.headers["Authorization"] == "Bearer ${access_token}"


def test_jwt_variant_auto_header():
    plan = draft_plan(_req(), _Fake(_auth_model("jwt")))
    assert plan.load_model.headers["Authorization"] == "Bearer ${jwt}"


def test_plain_token_still_works():
    plan = draft_plan(_req(), _Fake(_auth_model("token")))
    assert plan.load_model.headers["Authorization"] == "Bearer ${token}"


def test_yaml_openapi_import():
    spec = """openapi: 3.0.0
servers:
  - url: https://api.x.com/v1
paths:
  /products:
    get:
      summary: List
  /login:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                u:
                  type: string
"""
    r = import_endpoints("api.yaml", spec)
    assert r.base_url == "https://api.x.com/v1"
    paths = {(e.method, e.path) for e in r.endpoints}
    assert ("GET", "/products") in paths
    login = next(e for e in r.endpoints if e.path == "/login")
    assert login.example_body == {"u": "string"}
