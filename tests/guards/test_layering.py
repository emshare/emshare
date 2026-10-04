"""分层守卫：依赖方向一律指向内层，违反即失败。

domain ← core ← channels ← application
- domain 不可依赖 core/channels/application
- core 不可依赖 channels/application
- channels 不可依赖 application
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "em"

_ALLOWED = {
    "domain": {"domain"},
    "core": {"domain", "core"},
    "channels": {"domain", "core", "channels"},
    "application": {"domain", "core", "channels", "application"},
}


def _imported_layers(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    layers: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("em."):
            layers.append(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            layers.extend(a.name.split(".")[1] for a in node.names if a.name.startswith("em."))
    return layers


def test_layer_dependencies() -> None:
    violations: list[str] = []
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC)
        if len(rel.parts) == 1:  # 顶层门面（__init__ / __main__ / cli）允许引用任意层
            continue
        layer = rel.parts[0]
        allowed = _ALLOWED.get(layer)
        if allowed is None:
            continue
        for target in _imported_layers(path):
            if target not in allowed:
                violations.append(f"{rel}: {layer} 不得依赖 {target}")
    assert not violations, "分层违规:\n" + "\n".join(violations)
