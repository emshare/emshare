"""文档同步守卫：文档里的源码路径与文档链接必须指向真实存在的文件，违反即失败。

代码移动后若文档未同步更新，本测试报错。与 test_layering.py 同属 guards 套件。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "interfaces" / "eastmoney"

_SRC_PATH = re.compile(r"`([^`]*\.py)`")
_MD_LINK = re.compile(r"\]\(([^)]+\.md)\)")


def _check_source_path(raw: str) -> bool:
    """反引号里的 .py 路径必须指向真实文件；不含 / 的单独文件名跳过。"""
    if "/" not in raw:
        return True
    if (ROOT / raw).is_file():
        return True
    if raw.startswith("channels/"):
        return (ROOT / "src" / "em" / raw).is_file()
    return raw.startswith(("src/", "channels/")) is False


def _check_md_link(raw: str, current_doc: Path) -> bool:
    """markdown 链接里的 .md 路径必须指向真实文件。"""
    return (current_doc.parent / raw).resolve().is_file()


def test_docs_reference_existing_files() -> None:
    violations: list[str] = []
    for doc in DOCS.rglob("*.md"):
        text = doc.read_text(encoding="utf-8")
        for match in _SRC_PATH.finditer(text):
            raw = match.group(1)
            if not _check_source_path(raw):
                violations.append(f"{doc.relative_to(ROOT)}: 源码路径不存在 `{raw}`")
        for match in _MD_LINK.finditer(text):
            raw = match.group(1)
            if not _check_md_link(raw, doc):
                violations.append(f"{doc.relative_to(ROOT)}: 文档链接不存在 `{raw}`")
    assert not violations, "文档同步违规:\n" + "\n".join(violations)
