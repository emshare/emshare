"""pytest 全局配置：把 src 加入导入路径（pyproject 的 pythonpath 已声明，此处兜底）。"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
