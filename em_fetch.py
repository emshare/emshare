#!/usr/bin/env python3
"""命令行入口薄壳：保持 `python3 em_fetch.py ...` 用法兼容。

实际逻辑位于 ``src/em`` 包（domain / core / channels / application）。
也可用 ``python3 -m em <参数>`` 调用（先 ``pip install -e .``）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from em.cli import main

if __name__ == "__main__":
    sys.exit(main())
