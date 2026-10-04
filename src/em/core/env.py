"""轻量 .env 加载器：零依赖，``setdefault`` 语义（不覆盖已设环境变量）。

存在意义：``EM_PROXY_API`` 这类值含 ``&``，``source .env`` 会被 bash 当后台分隔符截断；
本模块在进程内按行解析，规避 shell 词法问题。仅在应用入口调用，不在 ``Settings.from_env``
里自动触发，以免污染单测的 ``monkeypatch`` 环境。
"""

import os
from pathlib import Path

_loaded = False


def load_dotenv(path: str | Path = ".env") -> None:
    """把 ``path`` 里的 ``KEY=VALUE`` 注入 ``os.environ``（已存在的键不覆盖）。

    - 跳过空行与 ``#`` 注释；
    - 按首个 ``=`` 切分，值原样保留（不去引号、不展开变量）；
    - 幂等：成功加载一次后不再重读；文件不存在时不锁，允许多候选路径轮询。
    """
    global _loaded
    if _loaded:
        return
    p = Path(path)
    if not p.is_file():
        return
    _loaded = True
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        os.environ.setdefault(key, value.strip())


def reset_for_test() -> None:
    """测试用：重置幂等标志以便重新加载。"""
    global _loaded
    _loaded = False
