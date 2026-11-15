"""pytest 全局配置：把 src 加入导入路径（pyproject 的 pythonpath 已声明，此处兜底）。"""

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

# 必须先于任何 `import em`：包入口会自动读取运行目录 / 仓库根的 .env，开发机上那是带真实
# 代理凭证的文件。测试不该读它，更不该因此真的去连代理源。需要验证自动加载的用例自行覆盖。
os.environ["EM_ENV_FILE"] = "none"

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def clean_em_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """从"没有任何 EM_ 配置、没加载过 .env"起步，用例结束后把环境还原。

    ``load_dotenv`` 直接写 ``os.environ``，monkeypatch 记不到那些键，所以收尾时把用例期间
    新冒出来的键删掉；原有的 ``EM_`` 变量经 monkeypatch 删除，由它负责恢复。
    """
    from em.core import env

    before = set(os.environ)
    for key in [k for k in os.environ if k.startswith("EM_")]:
        monkeypatch.delenv(key)
    env.reset_for_test()
    yield
    env.reset_for_test()
    for key in set(os.environ) - before:
        del os.environ[key]
