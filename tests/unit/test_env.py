"""env.load_dotenv 行为锁：setdefault 语义、幂等、跳过注释/export 前缀。"""

import os

from em.core.env import load_dotenv, reset_for_test


def _write(tmp_path, content: str):
    p = tmp_path / ".env"
    p.write_text(content, encoding="utf-8")
    return p


def test_loads_and_does_not_override_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("EM_FOO", "from_env")
    p = _write(tmp_path, "EM_FOO=from_file\nEM_BAR=from_file\n")
    reset_for_test()
    load_dotenv(p)
    assert os.environ["EM_FOO"] == "from_env"
    assert os.environ["EM_BAR"] == "from_file"


def test_skips_comments_and_blanks(tmp_path, monkeypatch):
    p = _write(tmp_path, "# 注释\n\nEM_X=1\nEM_Y=2\n")
    reset_for_test()
    monkeypatch.delenv("EM_X", raising=False)
    monkeypatch.delenv("EM_Y", raising=False)
    load_dotenv(p)
    assert os.environ["EM_X"] == "1"
    assert os.environ["EM_Y"] == "2"


def test_export_prefix_stripped(tmp_path, monkeypatch):
    p = _write(tmp_path, "export EM_Z=99\n")
    reset_for_test()
    monkeypatch.delenv("EM_Z", raising=False)
    load_dotenv(p)
    assert os.environ["EM_Z"] == "99"


def test_value_with_ampersand_preserved(tmp_path, monkeypatch):
    # 复现 .env 里 URL 含 & 的场景
    p = _write(tmp_path, "EM_PROXY_API=http://api/?act=get&num=1&time=30\n")
    reset_for_test()
    monkeypatch.delenv("EM_PROXY_API", raising=False)
    load_dotenv(p)
    assert os.environ["EM_PROXY_API"] == "http://api/?act=get&num=1&time=30"


def test_idempotent(tmp_path, monkeypatch):
    p = _write(tmp_path, "EM_ONCE=1\n")
    reset_for_test()
    monkeypatch.delenv("EM_ONCE", raising=False)
    load_dotenv(p)
    assert os.environ.get("EM_ONCE") == "1"
    # 第二次加载不应重新读盘（改文件也不影响）
    p.write_text("EM_ONCE=2\n", encoding="utf-8")
    load_dotenv(p)
    assert os.environ.get("EM_ONCE") == "1"


def test_missing_file_is_noop(tmp_path):
    reset_for_test()
    load_dotenv(tmp_path / "nonexistent.env")


def test_falls_through_to_second_candidate(tmp_path, monkeypatch):
    # 第一个路径不存在 → 不锁 → 第二个路径生效
    missing = tmp_path / "no.env"
    real = tmp_path / ".env"
    real.write_text("EM_FALLBACK=1\n", encoding="utf-8")
    reset_for_test()
    monkeypatch.delenv("EM_FALLBACK", raising=False)
    load_dotenv(missing)
    load_dotenv(real)
    assert os.environ.get("EM_FALLBACK") == "1"
