"""接口检索的行为锁（纯本地，不触网）。"""

import pytest

from em import interface_info, list_categories, search
from em.core.errors import InterfaceNotFoundError


def test_search_exact_name_top() -> None:
    rows = search("board_constituent_em")
    assert rows[0]["接口名"] == "board_constituent_em"
    assert rows[0]["匹配分"] >= 100.0


def test_search_by_keyword() -> None:
    rows = search("板块")
    assert rows and rows[0]["接口名"] == "board_constituent_em"


def test_search_market_by_keyword() -> None:
    rows = search("全市场 A股")
    assert rows and rows[0]["接口名"] == "stock_list_em"


def test_search_kline_by_keyword() -> None:
    rows = search("K线")
    assert rows and rows[0]["接口名"] == "kline_em"


def test_search_trends_by_keyword() -> None:
    rows = search("分时")
    assert rows and rows[0]["接口名"] == "trends_em"


def test_search_fund_flow_by_keyword() -> None:
    names = [r["接口名"] for r in search("fund_flow")]
    assert "fund_flow_em" in names
    assert "board_fund_flow_em" in names
    assert search("fund_flow_em")[0]["接口名"] == "fund_flow_em"


def test_search_board_fund_flow_by_keyword() -> None:
    rows = search("板块历史资金流")
    assert rows and rows[0]["接口名"] == "board_fund_flow_em"


def test_search_empty_query() -> None:
    assert search("") == []
    assert search("   ") == []


def test_search_negative_limit_raises() -> None:
    with pytest.raises(ValueError):
        search("board", limit=-1)


def test_search_category_filter() -> None:
    rows = search("股", category="market")
    assert all(r["类目"] == "market" for r in rows)
    assert search("股", category="nope") == []


def test_search_documented_only() -> None:
    rows = search("fetch", documented_only=True)
    assert all(r["有无文档"] for r in rows)


def test_interface_info_returns_full_record() -> None:
    info = interface_info("board_constituent_em")
    assert info["name"] == "board_constituent_em"
    assert info["category"] == "board"
    assert info["dataframe_variant"] == "df_board_constituent_em"
    assert len(info["inputs"]) == 4
    assert any(f["name"] == "main_net_inflow" for f in info["outputs"])
    assert "board_constituent_em(" in info["example"]


def test_interface_info_unknown_raises_with_hint() -> None:
    with pytest.raises(InterfaceNotFoundError) as exc:
        interface_info("fetch_nope")
    assert "候选" in str(exc.value)


def test_interface_info_kline() -> None:
    info = interface_info("kline_em")
    assert info["category"] == "kline"
    assert info["dataframe_variant"] == "df_kline_em"
    assert len(info["inputs"]) == 6
    assert any(f["name"] == "close" for f in info["outputs"])
    assert "kline_em(" in info["example"]


def test_interface_info_trends() -> None:
    info = interface_info("trends_em")
    assert info["category"] == "trends"
    assert info["dataframe_variant"] == "df_trends_em"
    assert len(info["inputs"]) == 5
    assert any(f["name"] == "avg_price" for f in info["outputs"])
    assert "trends_em(" in info["example"]


def test_interface_info_fund_flow() -> None:
    info = interface_info("fund_flow_em")
    assert info["category"] == "fund_flow"
    assert info["dataframe_variant"] == "df_fund_flow_em"
    assert len(info["inputs"]) == 2
    assert any(f["name"] == "xlarge_net_inflow" for f in info["outputs"])
    assert "fund_flow_em(" in info["example"]


def test_interface_info_board_fund_flow() -> None:
    info = interface_info("board_fund_flow_em")
    assert info["category"] == "fund_flow"
    assert info["dataframe_variant"] == "df_board_fund_flow_em"
    assert len(info["inputs"]) == 1
    assert info["inputs"][0]["name"] == "board"
    names = [f["name"] for f in info["outputs"]]
    assert len(names) == 11
    assert "main_net_inflow" in names
    assert "close" not in names
    assert "change_pct" not in names
    assert "board_fund_flow_em(" in info["example"]


def test_list_categories() -> None:
    cats = list_categories()
    assert cats == [
        {"类目": "board", "接口数": 1},
        {"类目": "fund_flow", "接口数": 2},
        {"类目": "kline", "接口数": 1},
        {"类目": "market", "接口数": 1},
        {"类目": "trends", "接口数": 1},
    ]


# -- DataFrame 包装（需 pandas，缺失则跳过）--

pd = pytest.importorskip("pandas")


def test_search_df_returns_dataframe() -> None:
    from em import search_df

    df = search_df("board_constituent_em")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["接口名", "类目", "描述", "有无文档", "匹配分"]
    assert df.iloc[0]["接口名"] == "board_constituent_em"


def test_list_categories_df_returns_dataframe() -> None:
    from em import list_categories_df

    df = list_categories_df()
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["类目", "接口数"]
    assert len(df) == 5


def test_interface_info_df_returns_param_and_field_tables() -> None:
    from em import interface_info_df

    tables = interface_info_df("board_constituent_em")
    assert set(tables) == {"inputs", "outputs"}
    assert isinstance(tables["inputs"], pd.DataFrame)
    assert isinstance(tables["outputs"], pd.DataFrame)
    assert list(tables["inputs"].columns) == ["名称", "类型", "必填", "默认值", "描述"]
    assert list(tables["outputs"].columns) == ["名称", "类型", "单位", "描述"]
    assert len(tables["inputs"]) == 4
    assert tables["inputs"].iloc[0]["名称"] == "board"
    assert any(tables["outputs"]["名称"] == "main_net_inflow")
