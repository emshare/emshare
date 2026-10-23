#!/usr/bin/env python3
"""采购账本报表：按源汇总跨天数据，决定主备顺序与是否换源。

用法：
    python3 tools/ledger_report.py                 # 默认读 EM_LEDGER_PATH / .em_ledger.jsonl
    python3 tools/ledger_report.py --limit 10      # 只看最近 10 次
    python3 tools/ledger_report.py --path /tmp/x.jsonl

判读：`每次进池` 越高、`淘汰率` 越低，说明该源买到的 IP 越值钱；
只有当两个源的出现次数都足够（≥3 次）时，比较才有意义。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from em.application.ledger import aggregate_sources, ledger_path, load


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="采购账本报表（按源汇总）")
    ap.add_argument("--path", default=None, help="账本文件；缺省取 EM_LEDGER_PATH / .em_ledger.jsonl")
    ap.add_argument("--limit", type=int, default=20, help="只看最近 N 次运行（默认 20）")
    args = ap.parse_args(argv)

    path = Path(args.path).expanduser() if args.path else ledger_path()
    if path is None:
        print("账本已关闭（EM_LEDGER_PATH=none）")
        return 1
    rows = load(path)
    if not rows:
        print(f"没有账本数据：{path}")
        return 1
    rows = rows[-max(args.limit, 1) :]

    pages = sum(int(r.get("pages", 0) or 0) for r in rows)
    returned = sum(int(r.get("ips_returned", 0) or 0) for r in rows)
    adopted = sum(int(r.get("ips_adopted", 0) or 0) for r in rows)
    productive = sum(int(r.get("ips_productive", 0) or 0) for r in rows)
    failed = sum(int(r.get("failed_attempts", 0) or 0) for r in rows)
    trips = sum(int(r.get("source_breaker_trips", 0) or 0) for r in rows)
    degraded = sum(int(r.get("degraded_adopted", 0) or 0) for r in rows)

    print(f"账本：{path}｜最近 {len(rows)} 次运行")
    print(
        f"总页数 {pages}｜采购 {returned}｜进池 {adopted}｜有产出 {productive}"
        f"｜单有效 IP {pages / max(productive, 1):.1f} 页"
        f"｜失败 {failed}｜熔断 {trips}｜降级放行 {degraded}"
    )
    print()
    print(f"{'源':<32}{'次数':>4}{'回源':>6}{'交付':>6}{'淘汰':>6}{'淘汰率':>8}{'进池':>6}{'每次进池':>10}")
    for name, stat in sorted(
        aggregate_sources(rows).items(), key=lambda kv: kv[1]["adopted_per_call"], reverse=True
    ):
        print(
            f"{name:<32}{int(stat['runs']):>4}{int(stat['calls']):>6}{int(stat['returned']):>6}"
            f"{int(stat['rejected']):>6}{stat['reject_rate']:>7.0%}{int(stat['adopted']):>6}"
            f"{stat['adopted_per_call']:>10.2f}"
        )
    print()
    print("提示：出现次数 <3 的源先不下结论；`每次进池` 是同一批里能用的 IP 数，越高越好。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
