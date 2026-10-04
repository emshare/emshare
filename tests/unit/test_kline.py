"""K 线映射、请求构建与周期/复权规范化的行为锁（用固定报文，不触网）。"""

import json
from pathlib import Path

import pytest

from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_stocks.kline.kline_em import (
    kline_request,
    normalize_adjust,
    normalize_period,
    secid_of,
)
from em.channels.eastmoney.mapping import to_kline_series
from em.domain.queries import KlineQuery

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "kline_daily.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_to_kline_series_maps_all_fields() -> None:
    series = to_kline_series(_load(), period="day", adjust="qfq")
    assert series.code == "000001"
    assert series.name == "平安银行"
    assert series.period == "day"
    assert series.adjust == "qfq"
    assert len(series.items) == 3


def test_to_kline_prices_are_not_scaled() -> None:
    last = to_kline_series(_load()).items[-1]
    assert last.date == "2024-12-31"
    assert last.open == pytest.approx(11.40)
    assert last.close == pytest.approx(11.32)
    assert last.high == pytest.approx(11.42)
    assert last.low == pytest.approx(11.28)
    assert last.volume == pytest.approx(90000.0)
    assert last.amount == pytest.approx(102000000.0)
    assert last.amplitude == pytest.approx(1.23)
    assert last.change_pct == pytest.approx(-0.70)
    assert last.change == pytest.approx(-0.08)
    assert last.turnover_rate == pytest.approx(0.46)


def test_short_kline_line_pads_with_none() -> None:
    data = {"rc": 0, "data": {"code": "x", "name": "y", "klines": ["2024-01-02,1.0"]}}
    kline = to_kline_series(data).items[0]
    assert kline.open == pytest.approx(1.0)
    assert kline.close is None
    assert kline.turnover_rate is None


def test_empty_klines() -> None:
    series = to_kline_series({"rc": 0, "data": {}})
    assert series.code == ""
    assert series.items == ()


def test_secid_of_by_market() -> None:
    assert secid_of(KlineQuery(code="000001", market="sz")) == "0.000001"
    assert secid_of(KlineQuery(code="600887", market="sh")) == "1.600887"
    assert secid_of(KlineQuery(code="830799", market="bj")) == "0.830799"
    assert secid_of(KlineQuery(code="000001", market="nope")) == "0.000001"


def test_normalize_period_and_adjust() -> None:
    assert normalize_period("week") == "week"
    assert normalize_period("quarter") == "day"
    assert normalize_adjust("hfq") == "hfq"
    assert normalize_adjust("weird") == "qfq"


def test_kline_request_default_day_qfq() -> None:
    request = kline_request(KlineQuery(code="000001", market="sz"))
    assert request.url() == f"{config.KLINE_HOST}{config.KLINE_PATH}"
    params = request.params()
    assert params["secid"] == "0.000001"
    assert params["klt"] == "101"
    assert params["fqt"] == "1"
    assert params["beg"] == "0"
    assert params["end"] == "20500101"
    assert params["rtntype"] == "6"
    assert params["fields2"] == config.KLINE_FIELDS2


def test_kline_request_week_hfq_mapping() -> None:
    request = kline_request(KlineQuery(code="600887", market="sh", period="week", adjust="hfq"))
    params = request.params()
    assert params["secid"] == "1.600887"
    assert params["klt"] == "102"
    assert params["fqt"] == "2"
    assert request.period == "week"
    assert request.adjust == "hfq"


def test_kline_request_unknown_falls_back() -> None:
    request = kline_request(KlineQuery(period="nope", adjust="nope"))
    assert request.klt == config.KLT_PERIODS["day"]
    assert request.fqt == config.FQT_ADJUSTS["qfq"]
    assert request.period == "day"
    assert request.adjust == "qfq"
