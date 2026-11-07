"""单位口径：统一「元 / % / 股」等，把渠道的放大整数在 mapping 内还原。"""

from typing import Annotated

# 换算系数
SHARES_PER_LOT = 100.0  # 手 -> 股
YUAN_PER_WAN = 1e4  # 万元 -> 元
YUAN_PER_YI = 1e8  # 亿元 -> 元
SCALED_INT = 100.0  # 东财 fltt=1 时价格/涨跌幅放大 100 倍的整数

# 单位别名：进入类型注解，使单位随模型可被机读
Yuan = Annotated[float | None, "unit:元"]
Pct = Annotated[float | None, "unit:%"]
Lot = Annotated[float | None, "unit:手"]
Point = Annotated[float | None, "unit:点"]  # 指数点位
Hkd = Annotated[float | None, "unit:港元"]
Shares = Annotated[float | None, "unit:股"]


def scaled(value: object, factor: float = SCALED_INT) -> float | None:
    """把放大整数还原为浮点；None 或不可转换一律返回 None，绝不臆造。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value) / factor  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def as_float(value: object) -> float | None:
    """安全转 float；None 或不可转换返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
