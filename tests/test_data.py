"""Tests for multi-format test-data loading and k6 parameterization."""

from __future__ import annotations

import pytest

from perfagent.contracts.load_model import (
    DataFile,
    LoadModel,
    LoadProfile,
    Scenario,
    Stage,
    Step,
)
from perfagent.data import DataValidationError, load_data, validate_fields_referenced
from perfagent.generator.k6_data import (
    body_to_k6_expr,
    k6_data_loader,
    path_to_k6_template,
    referenced_fields,
    uses_data,
)


# ---- loader: formats ----

def test_load_csv():
    d = load_data("u.csv", "username,pid\nalice,1\nbob,2")
    assert d.fields == ["username", "pid"]
    assert d.row_count == 2
    assert d.rows[0] == {"username": "alice", "pid": "1"}


def test_load_tsv():
    d = load_data("u.tsv", "a\tb\n1\t2")
    assert d.fields == ["a", "b"]
    assert d.rows[0] == {"a": "1", "b": "2"}


def test_load_txt_one_per_line():
    d = load_data("terms.txt", "shoes\nlaptop\n\nphone")
    assert d.fields == ["value"]
    assert [r["value"] for r in d.rows] == ["shoes", "laptop", "phone"]


def test_load_json_array():
    d = load_data("u.json", '[{"u":"a","n":1},{"u":"b","n":2}]')
    assert d.fields == ["u", "n"]
    assert d.rows[1] == {"u": "b", "n": 2}


def test_load_jsonl():
    d = load_data("u.jsonl", '{"u":"a"}\n{"u":"b"}')
    assert d.row_count == 2


def test_detect_by_content_when_extension_missing():
    d = load_data("data", "a,b\n1,2")   # no extension, comma content -> csv
    assert d.source_format == "csv"


# ---- loader: validation ----

def test_empty_file_rejected():
    with pytest.raises(DataValidationError):
        load_data("x.csv", "   ")


def test_header_only_rejected():
    with pytest.raises(DataValidationError):
        load_data("x.csv", "a,b,c")


def test_bad_jsonl_rejected():
    with pytest.raises(DataValidationError):
        load_data("x.jsonl", '{"a":1}\nnot-json')


def test_empty_column_name_rejected():
    with pytest.raises(DataValidationError):
        load_data("x.csv", "a,,c\n1,2,3")


def test_schema_hides_values():
    d = load_data("u.csv", "username,password\nalice,secret123")
    s = d.schema()
    assert s["fields"] == ["username", "password"]
    assert "secret123" not in str(s)   # only field names, never values


def test_validate_fields_referenced_catches_missing():
    d = load_data("u.csv", "username,pid\nalice,1")
    missing = validate_fields_referenced(d, {"username", "nonexistent"})
    assert missing == ["nonexistent"]


# ---- k6 parameterization ----

def _model_with_data():
    return LoadModel(
        target_base_url="http://x:8000",
        scenarios=[Scenario(name="s", steps=[
            Step(name="login", method="POST", path="/login",
                 body={"username": "${username}", "password": "${password}"}),
            Step(name="view", method="GET", path="/product/${product_id}"),
        ])],
        load_profile=LoadProfile(stages=[Stage(duration_seconds=10, target_users=5)]),
        data_file=DataFile(filename="users.csv",
                           fields=["username", "password", "product_id"],
                           row_count=100, source_format="csv"),
    )


def test_referenced_fields_found():
    assert referenced_fields(_model_with_data()) == {"username", "password", "product_id"}


def test_path_substitution():
    assert path_to_k6_template("/product/${product_id}") == "/product/${row.product_id}"


def test_body_quoted_placeholder_becomes_ref():
    out = body_to_k6_expr({"username": "${username}", "static": 5})
    assert "row.username" in out
    assert '"${username}"' not in out
    assert '"static": 5' in out


def test_body_inline_placeholder_becomes_template():
    out = body_to_k6_expr({"label": "user-${username}"})
    assert "`user-${row.username}`" in out


def test_loader_csv_uses_sharedarray_and_papaparse():
    ld = k6_data_loader(_model_with_data())
    assert "SharedArray" in ld
    assert "papaparse" in ld
    assert "open('./users.csv')" in ld


def test_uses_data_false_without_datafile():
    m = _model_with_data()
    m.data_file = None
    assert uses_data(m) is False
    assert k6_data_loader(m) == ""


def test_txt_loader_shape():
    m = _model_with_data()
    m.data_file = DataFile(filename="terms.txt", fields=["value"], source_format="txt")
    m.scenarios[0].steps = [Step(name="search", path="/search?q=${value}")]
    ld = k6_data_loader(m)
    assert "split('\\n')" in ld
    assert "value: v" in ld