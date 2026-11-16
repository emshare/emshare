"""采购账本落盘：每次全量拉取追加一行 JSONL，供跨天选源与成本核算。

为什么落盘：账本此前只进日志，跨天比较只能手抄或解析日志；而厂商按次计费，
"哪个源值得当主源"必须靠多天数据判断——单次运行的批次方差极大（实测淘汰率
30%~90%），一次跑得好坏说明不了源的质量差距。

写入失败只告警：账本是旁路观测，任何磁盘问题都不该影响取数。
默认按 XDG 落到用户数据目录，不再写进调用方的当前工作目录。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_ENV = "EM_LEDGER_PATH"
_DISABLED = ("", "none", "off", "0", "false")

# 旧版默认写 CWD 的 .em_ledger.jsonl；升级后可用 EM_LEDGER_PATH 指回旧文件继续累积。
_XDG_DATA_HOME = os.getenv("XDG_DATA_HOME")
DEFAULT_LEDGER_PATH = (
    (Path(_XDG_DATA_HOME) if _XDG_DATA_HOME else Path.home() / ".local" / "share")
    / "emshare"
    / "ledger.jsonl"
)


def ledger_path() -> Path | None:
    """账本文件路径；``EM_LEDGER_PATH`` 设为 none/off/0/空 时返回 None（关闭）。"""
    raw = os.getenv(_ENV)
    if raw is None:
        return Path(DEFAULT_LEDGER_PATH)
    value = raw.strip()
    if value.lower() in _DISABLED:
        return None
    return Path(value).expanduser()


def build_row(
    pool: dict[str, Any],
    timing: dict[str, float],
    pages: int,
    items: int,
    wall: float,
) -> dict[str, Any]:
    """组装一行账本（纯函数：字段即跨版本比对口径，改动会让历史数据无法合并）。"""
    return {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pages": pages,
        "items": items,
        "wall": round(wall, 3),
        "fetch_calls": int(pool.get("fetch_calls", 0) or 0),
        "ips_returned": int(pool.get("ips_returned", 0) or 0),
        "ips_unique": int(pool.get("ips_unique", 0) or 0),
        "history_truncated": bool(pool.get("history_truncated", False)),
        "prefilter_rejected": int(pool.get("prefilter_rejected", 0) or 0),
        "ips_adopted": int(pool.get("ips_adopted", 0) or 0),
        "ips_served": int(pool.get("ips_served", 0) or 0),
        "ips_productive": int(pool.get("ips_productive", 0) or 0),
        "soft_failures": int(pool.get("soft_failures", 0) or 0),
        "degraded_adopted": int(pool.get("degraded_adopted", 0) or 0),
        "degraded_events": int(pool.get("degraded_events", 0) or 0),
        "source_breaker_trips": int(pool.get("source_breaker_trips", 0) or 0),
        "refill_sec": round(float(pool.get("refill_sec", 0.0) or 0.0), 3),
        "prefilter_sec": round(float(pool.get("prefilter_sec", 0.0) or 0.0), 3),
        "proxy_requests": int(timing.get("proxy_requests", 0) or 0),
        "proxy_sec": round(float(timing.get("proxy_sec", 0.0) or 0.0), 3),
        "proxy_wait_sec": round(float(timing.get("proxy_wait_sec", 0.0) or 0.0), 3),
        "backoff_sec": round(float(timing.get("backoff_sec", 0.0) or 0.0), 3),
        "failed_attempts": int(timing.get("failed_attempts", 0) or 0),
        # 参与预筛的源：报表据此区分"淘汰率是测出来的"还是"根本没筛"
        "prefiltered": list(pool.get("prefiltered") or []),
        "sources": {name: dict(stat) for name, stat in (pool.get("source_stats") or {}).items()},
    }


def record(
    pool: dict[str, Any],
    timing: dict[str, float],
    pages: int,
    items: int,
    wall: float,
) -> None:
    """追加一行账本；任何写盘异常都只告警，不影响本次取数。"""
    path = ledger_path()
    if path is None:
        return
    row = build_row(pool, timing, pages, items, wall)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        log.warning("账本写入失败（不影响取数）: %s", exc)


def load(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL；损坏行（半行/手工编辑）直接跳过，不让一行脏数据毁掉整份报表。"""
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows


def aggregate_sources(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """按源聚合采购侧指标（淘汰率、每次回源进池数），供主备顺序决策。

    ``pref`` 标记该源是否参与过预筛（1=是）；``tagged`` 表示至少有一行带
    ``prefiltered`` 字段——旧账本没有该字段，只能标"未知"而不是"未预筛"。
    """
    agg: dict[str, dict[str, float]] = {}
    for row in rows:
        tagged = 1.0 if "prefiltered" in row else 0.0
        prefiltered = set(row.get("prefiltered") or [])
        for name, stat in (row.get("sources") or {}).items():
            item = agg.setdefault(
                name,
                {
                    "runs": 0.0,
                    "calls": 0.0,
                    "returned": 0.0,
                    "rejected": 0.0,
                    "adopted": 0.0,
                    "pref": 0.0,
                    "tagged": 0.0,
                },
            )
            calls = float(stat.get("calls", 0) or 0)
            item["runs"] += 1.0 if calls else 0.0
            item["calls"] += calls
            item["returned"] += float(stat.get("returned", 0) or 0)
            item["rejected"] += float(stat.get("rejected", 0) or 0)
            item["adopted"] += float(stat.get("adopted", 0) or 0)
            item["pref"] = max(item["pref"], 1.0 if name in prefiltered else 0.0)
            item["tagged"] = max(item["tagged"], tagged)
    for item in agg.values():
        returned = item["returned"]
        item["reject_rate"] = item["rejected"] / returned if returned else 0.0
        item["adopted_per_call"] = item["adopted"] / item["calls"] if item["calls"] else 0.0
    return agg
