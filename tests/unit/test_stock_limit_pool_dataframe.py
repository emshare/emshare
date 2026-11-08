"""涨跌停股池 DataFrame 适配的行为锁：每个股池只输出自己的列（不触网）。"""

import json
from pathlib import Path

import pytest

from em.application.dataframe import (
    LIMIT_POOL_COLUMNS_ZH,
    LIMIT_POOL_FIELDS_BY_TYPE,
    to_limit_pool_dataframe,
)
from em.channels.eastmoney.mapping import to_limit_pool_page
from em.domain.models import LimitPoolPage, LimitPoolStock

pd = pytest.importorskip("pandas")

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "push2ex_limit_pool.json"


def _page(pool_type: str) -> LimitPoolPage:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))[pool_type]
    return to_limit_pool_page(raw, pool_type, "20261106")


def test_limit_up_columns() -> None:
    df = to_limit_pool_dataframe(_page("limit_up"))
    assert list(df.columns) == [
        "代码",
        "名称",
        "市场",
        "涨跌幅",
        "最新价",
        "成交额",
        "流通市值",
        "总市值",
        "换手率",
        "封板资金",
        "首次封板时间",
        "最后封板时间",
        "炸板次数",
        "涨停统计-天数",
        "涨停统计-板数",
        "连板数",
        "所属行业",
    ]
    assert df.iloc[0]["首次封板时间"] == "09:25:00"
    assert df.iloc[0]["连板数"] == 5


def test_limit_down_uses_seal_order_label() -> None:
    df = to_limit_pool_dataframe(_page("limit_down"))
    assert "封单资金" in df.columns
    assert "封板资金" not in df.columns
    assert "涨停价" not in df.columns


@pytest.mark.parametrize("pool_type", list(LIMIT_POOL_FIELDS_BY_TYPE))
def test_each_pool_outputs_only_its_columns(pool_type: str) -> None:
    df = to_limit_pool_dataframe(_page(pool_type))
    assert len(df.columns) == len(LIMIT_POOL_FIELDS_BY_TYPE[pool_type])
    assert len(df) == 2
    # 每个股池列出的专属字段，在真实报文里都应有值（第一行）
    row = df.iloc[0]
    assert not pd.isna(row["最新价"])


def test_every_pool_field_has_a_label() -> None:
    for fields in LIMIT_POOL_FIELDS_BY_TYPE.values():
        for f in fields:
            assert f in LIMIT_POOL_COLUMNS_ZH
            assert hasattr(LimitPoolStock, f) or f in LimitPoolStock.__dataclass_fields__


def test_empty_pool_keeps_header() -> None:
    df = to_limit_pool_dataframe(LimitPoolPage(pool_type="broken", date="", total=0, items=()))
    assert df.empty
    assert len(df.columns) == len(LIMIT_POOL_FIELDS_BY_TYPE["broken"])
