"""Unit tests for validation, diffing, and parsing — no network required."""

from __future__ import annotations

from scrapeverse.brightdata import _parse_rows
from scrapeverse.pipeline import validate
from scrapeverse.store import diff_rows, has_changes


def test_validate_healthy():
    rows = [{"title": "A", "price": "$1"}, {"title": "B", "price": "$2"}, {"title": "C", "price": "$3"}]
    assert validate(rows, min_rows=3) is None


def test_validate_empty():
    assert "zero rows" in validate([], min_rows=3)


def test_validate_too_few_rows():
    msg = validate([{"title": "A"}], min_rows=3)
    assert msg is not None and "only 1 rows" in msg


def test_validate_empty_fields():
    rows = [
        {"title": "", "price": None},
        {"title": "", "price": None},
        {"title": "ok", "price": "1"},
    ]
    msg = validate(rows, min_rows=1)
    assert msg is not None and "empty" in msg


def test_parse_rows_plain_json():
    assert _parse_rows('[{"a":1}]') == [{"a": 1}]


def test_parse_rows_with_prefix():
    out = 'Collector c_123 done\n[{"a":1},{"b":2}]'
    assert len(_parse_rows(out)) == 2


def test_parse_rows_garbage():
    assert _parse_rows("not json at all") == []


def test_diff_added_removed_changed():
    old = [{"title": "A", "price": "$1"}, {"title": "B", "price": "$2"}]
    new = [{"title": "A", "price": "$9"}, {"title": "C", "price": "$3"}]
    d = diff_rows(old, new)
    assert [r["title"] for r in d["added"]] == ["C"]
    assert [r["title"] for r in d["removed"]] == ["B"]
    assert d["changed"][0]["after"]["price"] == "$9"
    assert has_changes(d)


def test_diff_no_changes():
    rows = [{"title": "A", "price": "$1"}]
    assert not has_changes(diff_rows(rows, rows))
