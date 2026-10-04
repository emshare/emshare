"""分时映射与请求构建的行为锁（用固定报文，不触网）。"""

import json
from pathlib import Path

import pytest

from em.channels.eastmoney import config
from em.channels.eastmoney.mapping import to_trend_series
from em.channels.eastmoney.trends.trends_em import secid_of, trends_request
from em.domain.queries import TrendQuery

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "trends_intraday.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_to_trend_series_maps_meta_and_items() -> None:
    series = to_trend_series(_load(), ndays=1)
    assert series.code == "000001"
    assert series.name == "平安银行"
    assert series.pre_close == pytest.approx(11.35)
    assert series.pre_price == pytest.approx(11.35)
    assert series.ndays == 1
    assert len(series.items) == 3


def test_to_trend_prices_not_scaled() -> None:
    first = to_trend_series(_load()).items[0]
    assert first.time == "2026-09-30 09:30"
    assert first.price == pytest.approx(11.36)
    assert first.avg_price == pytest.approx(11.36)
    assert first.high == pytest.approx(11.36)
    assert first.low == pytest.approx(11.36)
    assert first.volume == pytest.approx(2625.0)
    assert first.amount == pytest.approx(2982000.0)
    assert first.avg_price2 == pytest.approx(11.360)


def test_short_trend_line_pads_with_none() -> None:
    data = {
        "rc": 0,
        "data": {"code": "x", "name": "y", "preClose": 1.0, "trends": ["2026-09-30 09:30,11.0"]},
    }
    t = to_trend_series(data).items[0]
    assert t.price == pytest.approx(11.0)
    assert t.avg_price is None
    assert t.avg_price2 is None


def test_empty_trends() -> None:
    series = to_trend_series({"rc": 0, "data": {}})
    assert series.code == ""
    assert series.pre_close is None
    assert series.items == ()


def test_secid_of_by_market() -> None:
    assert secid_of(TrendQuery(code="000001", market="sz")) == "0.000001"
    assert secid_of(TrendQuery(code="600887", market="sh")) == "1.600887"
    assert secid_of(TrendQuery(code="830799", market="bj")) == "0.830799"
    assert secid_of(TrendQuery(code="000001", market="nope")) == "0.000001"


def test_trends_request_params() -> None:
    request = trends_request(TrendQuery(code="000001", market="sz", ndays=5))
    assert request.url() == f"{config.KLINE_HOST}{config.TRENDS_PATH}"
    params = request.params()
    assert params["secid"] == "0.000001"
    assert params["ndays"] == "5"
    assert params["iscr"] == "0"
    assert params["iscca"] == "0"
    assert params["fields2"] == config.TRENDS_FIELDS2
