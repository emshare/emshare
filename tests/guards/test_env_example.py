"""配置文件守卫：.env.example 必须能被 load_dotenv 正确解析为合法 Settings。"""

import os
from pathlib import Path

from em.core.env import load_dotenv, reset_for_test
from em.core.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_env_example_parses_to_valid_settings(monkeypatch) -> None:
    # 清空所有 EM_ 环境变量，确保只测 .env.example 本身
    for k in list(os.environ):
        if k.startswith("EM_"):
            monkeypatch.delenv(k, raising=False)
    reset_for_test()
    load_dotenv(ROOT / ".env.example")
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
    assert s.proxy_direct_fails == 2
    assert s.proxy_proxy_successes == 5
    assert s.proxy_cooldown_sec == 300
    assert s.proxy_prefilter_sources == 1  # 收费备用源默认不预筛
    assert s.proxy_degraded_mode == "lenient"  # 全死后改用 1.5s 快筛，不再放行未验证 IP
