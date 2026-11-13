"""接口检索的行为锁（纯本地，不触网）。"""

from dataclasses import MISSING

import pytest

from em import interface_info, list_categories, search
from em.core.errors import InterfaceNotFoundError


def test_search_exact_name_top() -> None:
    rows = search("board_constituent_em")
    assert rows[0]["接口名"] == "board_constituent_em"
    assert rows[0]["匹配分"] >= 100.0


def test_search_by_keyword() -> None:
    # 各板块接口对“板块”同分，同分按接口名排序（board_changes_em 排在最前）；加“成分股”即可区分
    names = [r["接口名"] for r in search("板块")[:2]]
    assert names == ["board_changes_em", "board_constituent_em"]
    assert search("板块 成分股")[0]["接口名"] == "board_constituent_em"


def test_search_market_by_keyword() -> None:
    rows = search("全市场 A股")
    assert rows and rows[0]["接口名"] == "stock_list_em"


def test_search_kline_by_keyword() -> None:
    # 个股与板块 K 线对“K线”同分，同分按接口名排序；加“个股”即可区分
    names = [r["接口名"] for r in search("K线")[:2]]
    assert set(names) == {"stock_kline_em", "board_kline_em"}
    assert search("个股 K线")[0]["接口名"] == "stock_kline_em"


def test_search_trends_by_keyword() -> None:
    rows = search("分时")
    assert rows and rows[0]["接口名"] == "stock_trends_em"


def test_search_fund_flow_by_keyword() -> None:
    names = [r["接口名"] for r in search("fund_flow")]
    assert "stock_fund_flow_em" in names
    assert "board_fund_flow_em" in names
    assert search("stock_fund_flow_em")[0]["接口名"] == "stock_fund_flow_em"


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
    info = interface_info("stock_kline_em")
    assert info["category"] == "kline"
    assert info["dataframe_variant"] == "df_stock_kline_em"
    assert len(info["inputs"]) == 6
    assert any(f["name"] == "close" for f in info["outputs"])
    assert "stock_kline_em(" in info["example"]


def test_interface_info_trends() -> None:
    info = interface_info("stock_trends_em")
    assert info["category"] == "trends"
    assert info["dataframe_variant"] == "df_stock_trends_em"
    assert len(info["inputs"]) == 5
    assert any(f["name"] == "avg_price" for f in info["outputs"])
    assert "stock_trends_em(" in info["example"]


def test_interface_info_fund_flow() -> None:
    info = interface_info("stock_fund_flow_em")
    assert info["category"] == "fund_flow"
    assert info["dataframe_variant"] == "df_stock_fund_flow_em"
    assert len(info["inputs"]) == 2
    assert any(f["name"] == "xlarge_net_inflow" for f in info["outputs"])
    assert "stock_fund_flow_em(" in info["example"]


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


def test_search_board_industry_list_by_keyword() -> None:
    rows = search("板块列表")
    assert rows and rows[0]["接口名"] == "board_industry_list_em"


def test_interface_info_board_industry_list() -> None:
    info = interface_info("board_industry_list_em")
    assert info["category"] == "board"
    assert info["dataframe_variant"] == "df_board_industry_list_em"
    assert len(info["inputs"]) == 5
    input_names = [p["name"] for p in info["inputs"]]
    assert input_names == ["board_type", "level", "sort", "page", "size"]
    out_names = [f["name"] for f in info["outputs"]]
    assert "up_count" in out_names
    assert "leader_name" in out_names
    assert "laggard_change_pct" in out_names
    assert "board_industry_list_em(" in info["example"]


def test_list_categories() -> None:
    cats = list_categories()
    assert cats == [
        {"类目": "billboard", "接口数": 10},
        {"类目": "board", "接口数": 2},
        {"类目": "changes", "接口数": 2},
        {"类目": "fund", "接口数": 1},
        {"类目": "fund_flow", "接口数": 2},
        {"类目": "hk", "接口数": 1},
        {"类目": "index", "接口数": 1},
        {"类目": "kline", "接口数": 2},
        {"类目": "market", "接口数": 1},
        {"类目": "pool", "接口数": 1},
        {"类目": "stock", "接口数": 2},
        {"类目": "trends", "接口数": 1},
    ]


def test_search_index_list_by_keyword() -> None:
    rows = search("指数列表")
    assert rows and rows[0]["接口名"] == "index_list_em"


def test_interface_info_index_list() -> None:
    info = interface_info("index_list_em")
    assert info["category"] == "index"
    assert info["dataframe_variant"] == "df_index_list_em"
    assert [p["name"] for p in info["inputs"]] == ["series", "sort", "page", "size"]
    units = {f["name"]: f["unit"] for f in info["outputs"]}
    assert len(units) == 14
    assert units["price"] == "点"
    assert units["turnover"] == "元"
    assert "market" in units
    assert "index_list_em(" in info["example"]


def test_search_hk_stock_list_by_keyword() -> None:
    rows = search("港股")
    assert rows and rows[0]["接口名"] == "hk_stock_list_em"


def test_interface_info_hk_stock_list() -> None:
    info = interface_info("hk_stock_list_em")
    assert info["category"] == "hk"
    assert info["dataframe_variant"] == "df_hk_stock_list_em"
    assert [p["name"] for p in info["inputs"]] == ["scope", "sort", "page", "size"]
    units = {f["name"]: f["unit"] for f in info["outputs"]}
    assert len(units) == 11
    assert units["price"] == "港元"
    assert units["turnover"] == "港元"
    assert units["volume"] == "股"
    assert "hk_stock_list_em(" in info["example"]


def test_search_fund_list_by_keyword() -> None:
    rows = search("ETF")
    assert rows and rows[0]["接口名"] == "fund_list_em"


def test_interface_info_fund_list() -> None:
    info = interface_info("fund_list_em")
    assert info["category"] == "fund"
    assert info["dataframe_variant"] == "df_fund_list_em"
    assert [p["name"] for p in info["inputs"]] == ["fund_type", "sort", "page", "size"]
    units = {f["name"]: f["unit"] for f in info["outputs"]}
    assert len(units) == 17
    assert units["price"] == "元"
    assert units["iopv"] == "元"
    assert units["discount_rate"] == "%"
    assert units["volume"] == "手"
    assert "fund_list_em(" in info["example"]


def test_search_limit_pool_by_keyword() -> None:
    rows = search("涨停")
    assert rows and rows[0]["接口名"] == "stock_limit_pool_em"


def test_interface_info_limit_pool() -> None:
    info = interface_info("stock_limit_pool_em")
    assert info["category"] == "pool"
    assert info["dataframe_variant"] == "df_stock_limit_pool_em"
    assert [p["name"] for p in info["inputs"]] == ["pool_type", "date"]
    names = [f["name"] for f in info["outputs"]]
    assert len(names) == 32
    assert "seal_fund" in names
    assert "limit_up_streak" in names
    assert "stock_limit_pool_em(" in info["example"]


def test_search_stock_info_and_bid_ask() -> None:
    assert search("五档")[0]["接口名"] == "stock_bid_ask_em"
    assert search("上市时间")[0]["接口名"] == "stock_info_em"


@pytest.mark.parametrize(("name", "n_outputs"), [("stock_info_em", 10), ("stock_bid_ask_em", 17)])
def test_interface_info_stock_get(name: str, n_outputs: int) -> None:
    info = interface_info(name)
    assert info["category"] == "stock"
    assert info["dataframe_variant"] == f"df_{name}"
    assert [p["name"] for p in info["inputs"]] == ["code", "market"]
    assert len(info["outputs"]) == n_outputs
    assert f"{name}(" in info["example"]


def test_search_changes_by_keyword() -> None:
    assert search("盘口异动")[0]["接口名"] == "stock_changes_em"
    assert search("板块异动")[0]["接口名"] == "board_changes_em"
    assert search("大笔买入")[0]["接口名"] == "stock_changes_em"
    # 盘口异动的描述不含“涨停”，检索“涨停”仍是股池排第一（见 test_search_limit_pool_by_keyword）
    assert "涨停" not in interface_info("stock_changes_em")["desc"]


def test_interface_info_stock_changes() -> None:
    from em.channels.eastmoney.ashare_stocks.stock_changes import STOCK_CHANGE_TYPES

    info = interface_info("stock_changes_em")
    assert info["category"] == "changes"
    assert info["dataframe_variant"] == "df_stock_changes_em"
    assert [p["name"] for p in info["inputs"]] == ["change_type"]
    # 参数说明列全 22 种异动类型
    assert all(t in info["inputs"][0]["desc"] for t in STOCK_CHANGE_TYPES)
    units = {f["name"]: f["unit"] for f in info["outputs"]}
    assert len(units) == 10
    assert units["volume"] == "股"
    assert units["change_pct"] == "%"
    assert "stock_changes_em(" in info["example"]


def test_interface_info_board_changes() -> None:
    info = interface_info("board_changes_em")
    assert info["category"] == "changes"
    assert info["dataframe_variant"] == "df_board_changes_em"
    assert info["inputs"] == ()
    units = {f["name"]: f["unit"] for f in info["outputs"]}
    assert len(units) == 10
    assert units["main_net_inflow"] == "元"  # 上游万元，已换算
    assert "type_counts" in units
    assert "board_changes_em(" in info["example"]


def test_search_billboard_by_keyword() -> None:
    assert search("龙虎榜")[0]["接口名"] == "billboard_detail_em"
    assert search("上榜原因")[0]["接口名"] == "billboard_detail_em"


def test_interface_info_billboard_detail_covers_model_fields() -> None:
    from dataclasses import fields

    from em.domain.models import BillboardEntry

    info = interface_info("billboard_detail_em")
    assert info["category"] == "billboard"
    assert info["dataframe_variant"] == "df_billboard_detail_em"
    assert [p["name"] for p in info["inputs"]] == ["start_date", "end_date"]
    assert [f["name"] for f in info["outputs"]] == [f.name for f in fields(BillboardEntry)]
    units = {f["name"]: f["unit"] for f in info["outputs"]}
    assert units["net_buy"] == "元" and units["net_buy_ratio"] == "%"
    assert "billboard_detail_em(" in info["example"]


_BILLBOARD_REPORTS = [
    # 接口, 模型, 入参, 检索词
    ("billboard_stock_stats_em", "BillboardStockStats", ["period"], "个股上榜统计"),
    (
        "billboard_institution_em",
        "BillboardInstitutionTrade",
        ["start_date", "end_date"],
        "机构买卖每日统计",
    ),
    ("billboard_institution_stats_em", "BillboardInstitutionStats", ["period"], "机构席位追踪"),
    (
        "billboard_branch_active_em",
        "BillboardBranchActive",
        ["start_date", "end_date"],
        "活跃营业部",
    ),
    ("billboard_branch_rank_em", "BillboardBranchRank", ["period"], "营业部排行"),
    ("billboard_branch_stats_em", "BillboardBranchStats", ["period"], "营业部统计"),
    (
        "billboard_branch_trades_em",
        "BillboardBranchTrade",
        ["branch_code", "start_date", "end_date"],
        "营业部详情",
    ),
    ("billboard_stock_dates_em", "BillboardStockDate", ["code"], "个股上榜日期"),
    ("billboard_stock_em", "BillboardSeat", ["code", "date", "side"], "个股龙虎榜详情"),
]


@pytest.mark.parametrize(
    "name,model,inputs,keyword", _BILLBOARD_REPORTS, ids=[r[0] for r in _BILLBOARD_REPORTS]
)
def test_interface_info_billboard_reports_cover_model_fields(
    name: str, model: str, inputs: list[str], keyword: str
) -> None:
    from dataclasses import fields

    import em
    from em.domain import models, queries

    info = interface_info(name)
    assert info["category"] == "billboard" and info["documented"] is True
    assert info["dataframe_variant"] == f"df_{name}"
    assert callable(getattr(em, name)) and callable(getattr(em, f"df_{name}"))
    # 入参与查询对象的字段一一对应，必填与否也一致
    query = getattr(queries, model_query_name(name))
    assert [p["name"] for p in info["inputs"]] == [f.name for f in fields(query)] == inputs
    required = [p["name"] for p in info["inputs"] if p["required"]]
    assert required == [f.name for f in fields(query) if f.default is MISSING]
    # 出参与模型字段一一对应
    assert [f["name"] for f in info["outputs"]] == [f.name for f in fields(getattr(models, model))]
    assert all(f["unit"] and f["desc"] for f in info["outputs"])
    assert f"{name}(" in info["example"]
    assert search(keyword)[0]["接口名"] == name


def model_query_name(interface: str) -> str:
    """billboard_branch_rank_em -> BillboardBranchRankQuery。"""
    stem = interface.removesuffix("_em")
    return "".join(part.capitalize() for part in stem.split("_")) + "Query"


def test_billboard_report_units() -> None:
    def units(name: str) -> dict[str, str]:
        return {f["name"]: f["unit"] for f in interface_info(name)["outputs"]}

    assert units("billboard_institution_em")["float_market_cap"] == "元"  # 上游亿元，已换算
    assert units("billboard_stock_em")["buy_ratio"] == "%"  # 上游比例，已换算
    assert units("billboard_branch_rank_em")["rise_prob_10d"] == "%"
    assert units("billboard_stock_stats_em")["billboard_times"] == "次"
    assert units("billboard_branch_active_em")["stock_codes"] == "—"


def test_search_billboard_family() -> None:
    # “龙虎榜”命中多个接口，同分按接口名排序，详情仍在最前；“营业部”命中 4 个营业部接口
    assert search("龙虎榜")[0]["接口名"] == "billboard_detail_em"
    assert [r["接口名"] for r in search("营业部")[:4]] == [
        "billboard_branch_active_em",
        "billboard_branch_rank_em",
        "billboard_branch_stats_em",
        "billboard_branch_trades_em",
    ]
    assert len(search("billboard", category="billboard")) == 10


def test_search_board_kline_by_keyword() -> None:
    rows = search("板块 K线")
    assert rows and rows[0]["接口名"] == "board_kline_em"


def test_interface_info_board_kline() -> None:
    info = interface_info("board_kline_em")
    assert info["category"] == "kline"
    assert info["dataframe_variant"] == "df_board_kline_em"
    assert [p["name"] for p in info["inputs"]] == ["board", "period", "beg", "end"]
    units = {f["name"]: f["unit"] for f in info["outputs"]}
    assert len(units) == 11
    # 板块是指数：价格类字段单位为点，成交额仍为元
    assert units["close"] == "点"
    assert units["change"] == "点"
    assert units["amount"] == "元"
    assert "board_kline_em(" in info["example"]


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
    assert len(df) == 12


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
