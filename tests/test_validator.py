"""Tests for the script validator (1 VU / 1 iteration smoke run)."""

from __future__ import annotations

from unittest import mock

from perfagent.runner import validator


def test_k6_missing_returns_clean_result():
    with mock.patch.object(validator, "k6_available", return_value=False):
        r = validator.validate_script("export default function(){}")
    assert r["ok"] is False
    assert r["status"] == "k6_missing"
    assert "k6" in r["message"]


def test_valid_script_when_k6_succeeds():
    fake = mock.Mock(returncode=0, stdout='{"scenarios":{"s1":{}}}', stderr="")
    with mock.patch.object(validator, "k6_available", return_value=True), \
         mock.patch.object(validator.subprocess, "run", return_value=fake):
        r = validator.validate_script("export default function(){}")
    assert r["ok"] is True
    assert r["status"] == "valid"


def test_failed_script_surfaces_error():
    fake = mock.Mock(returncode=255, stdout="", stderr="SyntaxError: unexpected token")
    with mock.patch.object(validator, "k6_available", return_value=True), \
         mock.patch.object(validator.subprocess, "run", return_value=fake):
        r = validator.validate_script("broken(")
    assert r["ok"] is False
    assert r["status"] == "failed"
    assert "SyntaxError" in r["detail"]


def test_timeout_is_handled():
    import subprocess
    with mock.patch.object(validator, "k6_available", return_value=True), \
         mock.patch.object(validator.subprocess, "run",
                           side_effect=subprocess.TimeoutExpired(cmd="k6", timeout=30)):
        r = validator.validate_script("while(true){}")
    assert r["ok"] is False
    assert r["status"] == "timeout"