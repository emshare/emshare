"""网络边界守卫：按函数限定会话创建/发送，禁止恢复隐式环境路由。

与 Ruff TID251、test_network_policy 的实际发送参数回归互补。
解析常规导入、别名、简单赋值和会话参数；不是任意 Python 动态代码的安全沙箱。
"""

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "em"
SESSION = "em.core.session.ExplicitProxySession"
RAW_SESSIONS = {
    "requests.Session",
    "requests.session",
    "requests.sessions.Session",
    "requests.sessions.session",
}
HTTP_METHODS = {"get", "post", "request", "send", "put", "patch", "delete", "head", "options"}
NETWORK_FILES = {
    "core/session.py",
    "core/transport.py",
    "core/proxy.py",
    "core/usage.py",
    "application/market_data.py",
    "application/resolve.py",
}
CREATORS = {
    ("application/market_data.py", "_create_client"),
    ("application/resolve.py", "_session"),
    ("core/usage.py", "ProxyUsage.refresh_balance"),
}
SENDERS = {
    ("core/transport.py", "HttpClient._attempt"),
    ("core/proxy.py", "fetch_proxies"),
    ("application/market_data.py", "_make_prober.probe"),
    ("core/usage.py", "ProxyUsage.refresh_balance"),
    ("application/resolve.py", "_search"),
}


class NetworkBoundary(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.scope = []
        self.names = {}
        self.errors = []
        self.creators = set()
        self.senders = set()

    @property
    def site(self):
        return self.filename, ".".join(self.scope)

    def reject(self, node, message):
        self.errors.append(f"{self.filename}:{node.lineno}: {message}")

    def ref(self, node):
        if isinstance(node, ast.Name):
            return self.names.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            if node.attr == "_session":
                return "@session"
            return f"{self.ref(node.value)}.{node.attr}"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return self.names.get(node.value, node.value)
        if isinstance(node, ast.Call):
            name = self.ref(node.func)
            if name in RAW_SESSIONS | {SESSION, "em.application.resolve._session"}:
                return "@session"
            if name == "_session" and self.filename == "application/resolve.py":
                return "@session"
            if name == "getattr" and len(node.args) == 2 and isinstance(node.args[1], ast.Constant):
                if node.args[1].value == "_session":
                    return "@session"
                return f"{self.ref(node.args[0])}.{node.args[1].value}"
        return ""

    def check_import(self, node, name):
        root = name.split(".")[0]
        if root == "requests" and self.filename not in NETWORK_FILES:
            self.reject(node, "业务模块不得依赖 requests；使用 HttpClient")
        if name.startswith("em.core.session") and self.filename not in NETWORK_FILES:
            self.reject(node, "业务模块不得取得底层会话；使用 HttpClient")
        if root in {"httpx", "aiohttp", "curl_cffi", "socket"} or name.startswith("urllib.request"):
            self.reject(node, "禁止旁路网络实现")
        if root == "urllib3" and not (
            self.filename == "core/transport.py" and name == "urllib3.exceptions.ReadTimeoutError"
        ):
            self.reject(node, "urllib3 只允许传输层引用 ReadTimeoutError")
        if name.startswith("http.client") and not (
            self.filename == "core/transport.py" and name == "http.client.RemoteDisconnected"
        ):
            self.reject(node, "http.client 只允许传输层引用断连异常")

    def visit_Import(self, node):
        for alias in node.names:
            self.check_import(node, alias.name)
            self.names[alias.asname or alias.name.split(".")[0]] = (
                alias.name if alias.asname else alias.name.split(".")[0]
            )

    def visit_ImportFrom(self, node):
        module = node.module or ""
        if node.level:
            package = "em." + str(Path(self.filename).parent).replace("/", ".")
            module = importlib.util.resolve_name("." * node.level + module, package)
        for alias in node.names:
            name = f"{module}.{alias.name}"
            self.check_import(node, name)
            self.names[alias.asname or alias.name] = name
            if alias.name == "*":
                self.reject(node, "禁止星号导入隐藏网络依赖")

    def visit_ClassDef(self, node):
        for base in node.bases:
            name = self.ref(base)
            if name in RAW_SESSIONS | {SESSION} and not (
                self.filename == "core/session.py"
                and node.name == "ExplicitProxySession"
                and name == "requests.Session"
            ):
                self.reject(node, "只允许 ExplicitProxySession 继承底层会话")
        self.visit_scope(node)

    def visit_scope(self, node):
        old_names = self.names.copy()
        self.scope.append(node.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
                if arg.arg == "session" or self.ref(arg.annotation) in RAW_SESSIONS | {SESSION}:
                    self.names[arg.arg] = "@session"
        self.generic_visit(node)
        self.scope.pop()
        self.names = old_names

    visit_FunctionDef = visit_scope
    visit_AsyncFunctionDef = visit_scope

    def bind(self, target, value):
        if isinstance(target, ast.Name):
            name = self.ref(value)
            if name:
                self.names[target.id] = name

    def visit_Assign(self, node):
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "trust_env"
                and not (
                    self.site == ("core/session.py", "ExplicitProxySession.__init__")
                    and self.ref(target.value) == "self"
                    and isinstance(node.value, ast.Constant)
                    and node.value.value is False
                )
            ):
                self.reject(node, "trust_env 仅允许在统一会话构造时设为 False")
            self.bind(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        # 与普通赋值共用策略，包括 s.trust_env: bool = True。
        assignment = ast.Assign(targets=[node.target], value=node.value)
        ast.copy_location(assignment, node)
        self.visit_Assign(assignment)

    def visit_With(self, node):
        for item in node.items:
            if item.optional_vars:
                self.bind(item.optional_vars, item.context_expr)
        self.generic_visit(node)

    def visit_Call(self, node):
        name = self.ref(node.func)
        if name == SESSION:
            self.creators.add(self.site)
            if self.site not in CREATORS:
                self.reject(node, "会话创建不在允许的装配函数内")
        if name in RAW_SESSIONS or (
            name.startswith(("requests.", "requests.api."))
            and name.rsplit(".", 1)[-1] in HTTP_METHODS
        ):
            self.reject(node, "禁止直接调用 requests；不得用 noqa 绕过")
        if name.startswith("@session.") and name.rsplit(".", 1)[-1] in HTTP_METHODS:
            self.senders.add(self.site)
            if self.site not in SENDERS:
                self.reject(node, "会话请求不在允许的网络发送函数内")
        if (
            name == "setattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "trust_env"
        ):
            self.reject(node, "不得动态修改 trust_env")
        if name in {
            "requests.utils.get_environ_proxies",
            "requests.sessions.get_environ_proxies",
            "requests.utils.resolve_proxies",
            "requests.sessions.resolve_proxies",
            "urllib.request.getproxies",
        }:
            self.reject(node, "不得手动恢复环境/系统代理")
        if name.startswith("pandas.read_"):
            # 当前产品没有文件读取入口；未来如需解析下载内容，应显式收敛为离线解析入口。
            self.reject(node, "pandas 文件读取须先明确离线解析入口，避免隐式下载")
        self.generic_visit(node)


def inspect_network(filename, text):
    visitor = NetworkBoundary(filename)
    visitor.visit(ast.parse(text))
    return visitor


def test_network_boundaries():
    errors, creators, senders = [], set(), set()
    for path in sorted(SRC.rglob("*.py")):
        visitor = inspect_network(
            path.relative_to(SRC).as_posix(), path.read_text(encoding="utf-8")
        )
        errors.extend(visitor.errors)
        creators.update(visitor.creators)
        senders.update(visitor.senders)
    assert not errors, "网络边界违规：\n" + "\n".join(errors)
    assert creators == CREATORS, "会话创建入口变化，请同步边界清单与文档"
    assert senders == SENDERS, "网络发送入口变化，请同步边界清单与文档"


@pytest.mark.parametrize(
    ("filename", "code"),
    [
        ("channels/eastmoney/new.py", "import requests as r\nr.get('https://example.test')"),
        (
            "application/market_data.py",
            "from requests import get as fetch\nfetch('https://example.test')",
        ),
        ("application/market_data.py", "import requests\ns = requests.Session()  # noqa: TID251"),
        (
            "application/market_data.py",
            "from em.core.session import ExplicitProxySession as S\ndef new():\n    return S()",
        ),
        (
            "channels/eastmoney/new.py",
            "from ...core.session import ExplicitProxySession as S\ns = S()",
        ),
        (
            "application/market_data.py",
            "def new(session):\n    fetch = session.get\n    fetch('https://example.test')",
        ),
        (
            "channels/eastmoney/new.py",
            "def fetch(client):\n    s = client._session\n    return s.get('https://example.test')",
        ),
        ("application/market_data.py", "def new(session):\n    session.trust_env = True"),
        ("core/session.py", "def new(session):\n    session.trust_env: bool = True"),
        (
            "application/market_data.py",
            "def new(session):\n    setattr(session, 'trust_env', True)",
        ),
        ("core/session.py", "import requests\nclass Other(requests.Session):\n    pass"),
        (
            "application/new.py",
            "from urllib.request import urlopen as fetch\nfetch('https://example.test')",
        ),
        ("application/new.py", "import httpx\nhttpx.get('https://example.test')"),
        ("core/session.py", "from http.client import HTTPSConnection"),
        (
            "application/market_data.py",
            "from requests.utils import get_environ_proxies as env\nenv('https://example.test')",
        ),
        (
            "application/market_data.py",
            "def new(session):\n    fetch = getattr(session, 'get')\n    fetch('https://example.test')",
        ),
        ("application/new.py", "import pandas as pd\npd.read_csv('https://example.test')"),
    ],
)
def test_guard_rejects_bypasses(filename, code):
    assert inspect_network(filename, code).errors


@pytest.mark.parametrize(
    ("filename", "code"),
    [
        (
            "channels/eastmoney/new.py",
            "def fetch(client):\n    return client.get_text('https://example.test', {}, {})",
        ),
        ("application/new.py", "def lookup(row):\n    return row.get('http')"),
        ("core/transport.py", "from urllib3.exceptions import ReadTimeoutError"),
        (
            "core/transport.py",
            "class HttpClient:\n    def _attempt(self):\n        return self._session.get('https://example.test')",
        ),
        (
            "application/resolve.py",
            "from em.core.session import ExplicitProxySession\ndef _session():\n    return ExplicitProxySession()",
        ),
        (
            "core/session.py",
            "import requests\nclass ExplicitProxySession(requests.Session):\n    def __init__(self):\n        self.trust_env = False",
        ),
    ],
)
def test_guard_accepts_allowed_paths(filename, code):
    assert not inspect_network(filename, code).errors


@pytest.mark.parametrize(
    ("filename", "code"),
    [
        ("src/em/channels/eastmoney/new.py", "import requests as r\nr.get('https://example.test')"),
        (
            "src/em/application/market_data.py",
            "from requests import post as send\nsend('https://example.test')",
        ),
        ("src/em/core/transport.py", "from requests.sessions import Session as S\nS()"),
        ("src/em/core/session.py", "import requests\nrequests.get('https://example.test')"),
        ("src/em/application/new.py", "import httpx\nhttpx.Client()"),
    ],
)
def test_ruff_config_rejects_network_bypass(filename, code):
    # 使用项目的真实配置，不强制 --select；删掉规则或扩大文件豁免会导致回归失败。
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--config",
            str(ROOT / "pyproject.toml"),
            "--stdin-filename",
            filename,
            "--output-format",
            "json",
            "-",
        ],
        input=code,
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 1, result.stderr or result.stdout
    assert any(diagnostic["code"] == "TID251" for diagnostic in json.loads(result.stdout))
