"""映射与单位换算的行为锁（用固定报文，不触网）。"""

import json
from pathlib import Path

import pytest

from em.channels.eastmoney.mapping import is_ok, parse_jsonp, to_quote_page

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "clist_board.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_jsonp_extracts_payload() -> None:
    data = _load()
    text = f"cb({json.dumps(data, ensure_ascii=False)});"
    assert parse_jsonp(text) == data
    assert parse_jsonp("not jsonp") is None


def test_parse_jsonp_rejects_non_object_json() -> None:
    assert parse_jsonp("[1, 2, 3]") is None
    assert parse_jsonp("123") is None
    assert parse_jsonp('"text"') is None


def test_is_ok() -> None:
    assert is_ok({"rc": 0}) is True
    assert is_ok({"rc": 1}) is False
    assert is_ok(None) is False


def test_scaled_int_and_units() -> None:
    page = to_quote_page(_load(), flow_field="f174")
    assert page.total == 2
    first = page.items[0]
    assert first.code == "600887"
    assert first.name == "伊利股份"
    assert first.price == pytest.approx(27.30)
    assert first.change_pct == pytest.approx(0.22)
    assert first.main_net_inflow == pytest.approx(695959104.0)
    assert first.turnover == pytest.approx(411668717.8)
    assert first.turnover_rate == pytest.approx(2.96)


def test_missing_fields_are_none() -> None:
    data = {"rc": 0, "data": {"total": 1, "diff": [{"f12": "x", "f14": "y"}]}}
    quote = to_quote_page(data).items[0]
    assert quote.price is None
    assert quote.change_pct is None
    assert quote.main_net_inflow is None
