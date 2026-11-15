"""轻量 .env 加载器：零依赖，``setdefault`` 语义（不覆盖已设环境变量）。

存在意义：``EM_PROXY_API`` 这类值含 ``&``，``source .env`` 会被 bash 当后台分隔符截断；
本模块在进程内按行解析，规避 shell 词法问题。

``import em`` 时由包入口调用一次 ``autoload``（命令行同样先经过包入口），库调用与命令行
因此读到同一份配置。不在 ``Settings.from_env`` 里触发：那会让每次取配置都带上读盘副作用，
也会污染单测的 ``monkeypatch`` 环境（测试用 ``EM_ENV_FILE=none`` 关掉自动加载）。
"""

import locale
import logging
import os
from importlib.resources import files
from pathlib import Path

log = logging.getLogger(__name__)

# 指定 .env 的位置；设为 none / off / 0 / false / 空则完全不读（口径同 EM_LEDGER_PATH）
ENV_FILE_VAR = "EM_ENV_FILE"
_DISABLED = ("", "none", "off", "0", "false")
# 自动加载只取本库自己的变量：运行目录下的 .env 可能属于别的项目，把其中的
# DATABASE_URL / HTTP_PROXY 之类注入进程环境会改变无关代码的行为
_AUTOLOAD_PREFIX = "EM_"
_TEMPLATE = "env.example"

_loaded = False
_loaded_path: Path | None = None
_loaded_keys = 0  # 已加载文件里被采纳的键数（按前缀过滤后）；0 说明文件里没有本库的配置


def _read(path: Path) -> str:
    """读出文本：UTF-8（容忍 BOM）优先，其次 UTF-16（认 BOM），最后按本地编码兜底。

    Windows 上常见三种情况：记事本带 BOM 保存（BOM 会粘在首行键名上，对不上 ``EM_`` 前缀）、
    按本地编码（如 GBK）保存（中文注释在 UTF-8 下解码失败）、PowerShell 5 用 ``>`` 重定向
    写出 UTF-16。键和值基本是 ASCII，兜底解码即使把注释解花了也不影响取值。
    """
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode(locale.getpreferredencoding(False), errors="replace")


def load_dotenv(path: str | Path = ".env", *, prefix: str | None = None) -> bool:
    """把 ``path`` 里的 ``KEY=VALUE`` 注入 ``os.environ``（已存在的键不覆盖），返回本次是否加载。

    - 跳过空行与 ``#`` 注释；
    - 按首个 ``=`` 切分，值原样保留（不去引号、不展开变量）；
    - ``prefix`` 非空时只取以它开头的键，其余行忽略；
    - 幂等：成功加载一次后不再重读；文件不存在时不锁，允许多候选路径轮询。
    """
    global _loaded, _loaded_path, _loaded_keys
    if _loaded:
        return False
    p = Path(path)
    if not p.is_file():
        return False
    text = _read(p)  # 先读后锁：读盘失败时不能留下"已加载"的假状态
    _loaded = True
    _loaded_path = _absolute(p)
    _loaded_keys = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if not key or (prefix and not key.startswith(prefix)):
            continue
        value = value.strip()
        if "\x00" in key or "\x00" in value:  # 环境变量不能含 NUL，写进去会直接抛错
            continue
        os.environ.setdefault(key, value)
        _loaded_keys += 1
    return True


def _absolute(path: Path) -> Path:
    try:
        return path.absolute()
    except OSError:  # 当前目录已被删除：取不到绝对路径，原样返回
        return path


def _checkout_root() -> Path | None:
    """源码检出的仓库根（``<root>/src/em/core/env.py``）；装进 site-packages 后没有，返回 None。"""
    root = Path(__file__).resolve().parents[3]
    if (root / "pyproject.toml").is_file() and (root / "src" / "em").is_dir():
        return root
    return None


def search_paths() -> list[Path]:
    """自动加载依次查找的 .env 位置；``EM_ENV_FILE`` 设为关闭值时为空。

    未设 ``EM_ENV_FILE``：先看运行目录，源码检出时再回退到仓库根（便于从任意目录跑脚本）。
    设了路径：只认那一个文件。
    """
    raw = os.getenv(ENV_FILE_VAR)
    if raw is not None:
        value = raw.strip()
        if value.lower() in _DISABLED:
            return []
        try:
            explicit = Path(value).expanduser()
        except RuntimeError:  # ~ 展不开（取不到家目录）：按字面路径处理
            explicit = Path(value)
        return [_absolute(explicit)]
    paths = [_absolute(Path(".env"))]
    root = _checkout_root()
    if root is not None and root / ".env" not in paths:
        paths.append(root / ".env")
    return paths


def autoload() -> Path | None:
    """按约定位置加载 .env（只取 ``EM_`` 开头的键），返回实际加载的文件；没加载则 None。

    在包被导入时调用，所以读不了、内容有问题都只告警、不抛出：
    配置文件出问题不该让 ``import em`` 失败。
    """
    if _loaded:
        return _loaded_path
    paths = search_paths()
    if paths and os.getenv(ENV_FILE_VAR) is not None and not paths[0].is_file():
        log.warning("%s 指向的文件不存在：%s（未加载任何 .env）", ENV_FILE_VAR, paths[0])
        return None
    for path in paths:
        try:
            if load_dotenv(path, prefix=_AUTOLOAD_PREFIX):
                break
        except (OSError, ValueError) as exc:  # ValueError：值超出系统对环境变量的限制等
            log.warning("读取 %s 失败，已跳过：%s", path, exc)
    return _loaded_path


def loaded_path() -> Path | None:
    """本进程实际加载的 .env；没有加载过则为 None。"""
    return _loaded_path


def loaded_keys() -> int:
    """已加载的 .env 里被采纳的键数；文件属于别的项目（没有 ``EM_`` 配置）时为 0。"""
    return _loaded_keys


def template_text() -> str:
    """随包分发的 .env 模板全文（``emshare --init-env`` 写出的就是它）。"""
    return files("em").joinpath(_TEMPLATE).read_text(encoding="utf-8")


def reset_for_test() -> None:
    """测试用：重置幂等标志以便重新加载。"""
    global _loaded, _loaded_path, _loaded_keys
    _loaded = False
    _loaded_path = None
    _loaded_keys = 0
