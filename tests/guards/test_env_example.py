"""配置模板守卫：随包分发的 env.example 必须能被 load_dotenv 正确解析为合法 Settings。"""

from pathlib import Path

from em.application.hints import egress_hint
from em.core import env
from em.core.env import load_dotenv
from em.core.errors import NetworkError
from em.core.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "src" / "em" / "env.example"


def test_env_example_parses_to_valid_settings(clean_em_env) -> None:
    load_dotenv(TEMPLATE)
    # 不应抛 ConfigError（如 "10# 退避" 这种粘连会导致 int 解析失败）
    s = Settings.from_env()
    assert s.max_retries == 4
    # 读超时同时是预筛探测的读取预算：需覆盖整页耗时（实测经代理 0.79~1.25s），
    # 2s 只高于均值 1.6 倍，慢页会被误判成超时并触发换 IP
    assert s.request_timeout_sec == 3
    assert s.backoff_sec == 0.2
    assert s.backoff_cap_sec == 2.0
    assert s.backoff_jitter_sec == 0.1
    assert s.proxy_timeout_sec == 8
    assert s.proxy_mode == "auto"
    assert s.proxy_direct_fails == 1
    assert s.proxy_proxy_successes == 5
    assert s.proxy_cooldown_sec == 300
    assert s.proxy_prefilter_sources == 1  # 收费备用源默认不预筛
    assert s.proxy_prefilter_target == 1  # 探到 1 个活 IP 即停，其余留作预留
    assert s.proxy_degraded_mode == "lenient"  # 全死后改用 1.5s 快筛，不再放行未验证 IP


def test_packaged_template_is_the_tracked_file() -> None:
    # emshare --init-env 写出的内容来自包资源；它必须就是仓库里维护的这一份
    assert env.template_text() == TEMPLATE.read_text(encoding="utf-8")


def test_only_keys_with_em_prefix(clean_em_env) -> None:
    # 自动加载只取 EM_ 开头的键：模板里若混进别的键，生成的 .env 里那一行会被悄悄忽略
    keys = [
        line.split("=", 1)[0].lstrip("# ").strip()
        for line in TEMPLATE.read_text(encoding="utf-8").splitlines()
        if "=" in line and line.lstrip("# ").startswith(("EM_", "export "))
    ]
    assert keys
    assert all(k.startswith("EM_") for k in keys)


def test_unedited_template_is_reported_as_placeholder(clean_em_env) -> None:
    # 生成 .env 后没改就去用：提示必须点明"还是占位符"，而不是当成已配置好而沉默
    load_dotenv(TEMPLATE, prefix="EM_")
    hint = egress_hint(NetworkError("连接断开"), Settings.from_env())
    assert hint is not None
    assert "占位符" in hint
