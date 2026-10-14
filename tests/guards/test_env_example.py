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
    assert s.request_timeout_sec == 2
    assert s.backoff_sec == 0.2
    assert s.backoff_cap_sec == 2.0
    assert s.backoff_jitter_sec == 0.1
    assert s.proxy_timeout_sec == 8
    assert s.proxy_mode == "auto"
    assert s.proxy_direct_fails == 3
    assert s.proxy_proxy_successes == 5
    assert s.proxy_cooldown_sec == 300
