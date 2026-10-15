"""Tests for endpoint importers — OpenAPI, Postman, HAR."""

from __future__ import annotations

import json

import pytest

from perfagent.importers import ImportError_, import_endpoints


def test_openapi_import():
    spec = json.dumps({
        "openapi": "3.0.0",
        "servers": [{"url": "https://api.x.com/v1"}],
        "paths": {
            "/products": {"get": {"summary": "List"}},
            "/login": {"post": {"requestBody": {"content": {"application/json": {
                "schema": {"type": "object", "properties": {"u": {"type": "string"}}}}}}}},
        },
    })
    r = import_endpoints("api.json", spec)
    assert r.base_url == "https://api.x.com/v1"
    paths = {(e.method, e.path) for e in r.endpoints}
    assert ("GET", "/products") in paths
    login = next(e for e in r.endpoints if e.path == "/login")
    assert login.example_body == {"u": "string"}


def test_swagger2_import():
    spec = json.dumps({
        "swagger": "2.0", "host": "api.x.com", "basePath": "/v2", "schemes": ["https"],
        "paths": {"/ping": {"get": {}}},
    })
    r = import_endpoints("s.json", spec)
    assert r.base_url == "https://api.x.com/v2"
    assert r.endpoints[0].path == "/ping"


def test_postman_import_with_folders():
    col = json.dumps({
        "info": {"_postman_id": "1", "name": "C", "schema": "x"},
        "item": [
            {"name": "P", "request": {"method": "GET", "url": {"raw": "https://a.com/products", "path": ["products"]}}},
            {"name": "F", "item": [
                {"name": "L", "request": {"method": "POST", "url": {"path": ["login"]},
                 "body": {"mode": "raw", "raw": "{\"u\":1}"}}}]},
        ],
    })
    r = import_endpoints("c.json", col)
    assert len(r.endpoints) == 2
    assert r.base_url == "https://a.com"
    login = next(e for e in r.endpoints if e.path == "/login")
    assert login.example_body == {"u": 1}


def test_har_import_skips_assets_and_dupes():
    har = json.dumps({"log": {"entries": [
        {"request": {"method": "GET", "url": "https://a.com/products"}},
        {"request": {"method": "GET", "url": "https://a.com/app.js"}},
        {"request": {"method": "POST", "url": "https://a.com/login", "postData": {"text": "{\"u\":1}"}}},
        {"request": {"method": "GET", "url": "https://a.com/products"}},
    ]}})
    r = import_endpoints("s.har", har)
    paths = {(e.method, e.path) for e in r.endpoints}
    assert paths == {("GET", "/products"), ("POST", "/login")}


def test_unknown_format_rejected():
    with pytest.raises(ImportError_):
        import_endpoints("x.json", '{"random":"json"}')


def test_empty_rejected():
    with pytest.raises(ImportError_):
        import_endpoints("x.json", "   ")
