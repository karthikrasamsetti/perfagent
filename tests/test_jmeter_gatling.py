"""Tests for the JMeter and Gatling renderers."""

from __future__ import annotations

import xml.dom.minidom

from perfagent.contracts.load_model import (
    Assertion, LoadModel, LoadProfile, LoadProfileType, Scenario, Stage, Step,
)
from perfagent.generator.gatling_renderer import render_gatling
from perfagent.generator.jmeter_renderer import render_jmeter


def _model():
    return LoadModel(
        target_base_url="https://api.shop.com:8443/v1",
        scenarios=[
            Scenario(name="Browsing", weight=0.7, steps=[
                Step(name="view", method="GET", path="/products")]),
            Scenario(name="Checkout", weight=0.3, steps=[
                Step(name="login", method="POST", path="/login", body={"user": "demo"},
                     assertions=[Assertion(kind="status", op="eq", value="200")]),
                Step(name="pay", method="POST", path="/checkout",
                     body={"order": "${uuid}", "amt": "${randomInt(1,100)}"},
                     assertions=[Assertion(kind="body_contains", value="orderId")])]),
        ],
        load_profile=LoadProfile(type=LoadProfileType.RAMP, stages=[
            Stage(duration_seconds=4, target_users=10),
            Stage(duration_seconds=12, target_users=10),
            Stage(duration_seconds=4, target_users=0)]),
    )


def test_jmeter_valid_xml():
    jmx = render_jmeter(_model())
    xml.dom.minidom.parseString(jmx)   # raises if not well-formed


def test_jmeter_has_thread_groups_and_host():
    jmx = render_jmeter(_model())
    assert "Browsing" in jmx and "Checkout" in jmx
    assert "ThreadGroup" in jmx
    assert "api.shop.com" in jmx and "8443" in jmx


def test_jmeter_maps_generators_and_assertions():
    jmx = render_jmeter(_model())
    assert "__UUID()" in jmx
    assert "__Random(1,100)" in jmx
    assert "ResponseAssertion" in jmx


def test_gatling_simulation_structure():
    sc = render_gatling(_model())
    assert "extends Simulation" in sc
    assert 'scenario("Browsing")' in sc
    assert ".exec(http(" in sc
    assert "rampUsers" in sc


def test_gatling_checks():
    sc = render_gatling(_model())
    assert "status.in(200 to 399)" in sc
    assert "status.is(200)" in sc
    assert 'substring("orderId")' in sc
