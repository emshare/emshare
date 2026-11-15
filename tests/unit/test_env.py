"""env 行为锁：load_dotenv 的 setdefault 语义 / 幂等 / 前缀过滤 / 编码容错，
以及 import em 时的自动加载（查找位置、EM_ENV_FILE、失败不抛）。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from em.core import env
from em.core.env import load_dotenv, reset_for_test
from em.core.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


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


# --- 返回值 / 前缀过滤 / 编码容错 ---


def test_returns_whether_this_call_loaded(tmp_path, clean_em_env):
    assert load_dotenv(tmp_path / "missing.env") is False
    p = _write(tmp_path, "EM_A=1\n")
    assert load_dotenv(p) is True
    assert load_dotenv(p) is False  # 幂等：第二次不再读盘


def test_prefix_keeps_only_matching_keys(tmp_path, clean_em_env):
    # 运行目录下的 .env 可能是别的项目的：自动加载只能取本库的变量
    p = _write(tmp_path, "OTHER_PROJECT_KEY_7F3A=secret\nEM_ONLY=1\nexport OTHER_EXPORTED_7F3A=x\n")
    load_dotenv(p, prefix="EM_")
    assert os.environ["EM_ONLY"] == "1"
    assert "OTHER_PROJECT_KEY_7F3A" not in os.environ
    assert "OTHER_EXPORTED_7F3A" not in os.environ
    assert env.loaded_keys() == 1


def test_utf8_bom_does_not_hide_first_key(tmp_path, clean_em_env):
    # 记事本"带 BOM 保存"：BOM 粘在首行键名上会让它对不上前缀，整行被悄悄丢掉
    p = tmp_path / ".env"
    p.write_bytes("EM_FIRST=1\nEM_SECOND=2\n".encode("utf-8-sig"))
    load_dotenv(p, prefix="EM_")
    assert os.environ["EM_FIRST"] == "1"
    assert os.environ["EM_SECOND"] == "2"


def test_non_utf8_comments_do_not_break_loading(tmp_path, clean_em_env):
    # 按本地编码（如 GBK）保存的文件：中文注释解不开也不能影响取值，更不能抛错
    p = tmp_path / ".env"
    p.write_bytes("# 代理配置\nEM_GBK=http://api/?a=1&b=2\n".encode("gbk"))
    load_dotenv(p, prefix="EM_")
    assert os.environ["EM_GBK"] == "http://api/?a=1&b=2"


def test_utf16_file_is_readable(tmp_path, clean_em_env):
    # PowerShell 5 的 `>` 重定向写出的是带 BOM 的 UTF-16
    p = tmp_path / ".env"
    p.write_bytes("EM_U16=1\r\nEM_U16_B=2\r\n".encode("utf-16"))
    load_dotenv(p, prefix="EM_")
    assert os.environ["EM_U16"] == "1"
    assert os.environ["EM_U16_B"] == "2"


# --- autoload：import em 时走的那条路 ---


@pytest.fixture
def in_tmp_cwd(tmp_path, monkeypatch, clean_em_env):
    """切到空目录并屏蔽"仓库根回退"，让查找位置只剩运行目录。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(env, "_checkout_root", lambda: None)
    return tmp_path


def test_autoload_reads_env_in_cwd(in_tmp_cwd):
    _write(in_tmp_cwd, "EM_PROXY_API=http://api/?a=1&b=2\nOTHER_PROJECT_KEY_7F3A=secret\n")
    loaded = env.autoload()
    assert loaded == Path.cwd() / ".env"
    assert env.loaded_path() == loaded
    assert os.environ["EM_PROXY_API"] == "http://api/?a=1&b=2"
    assert "OTHER_PROJECT_KEY_7F3A" not in os.environ  # 只取 EM_ 开头的
    assert Settings.from_env().proxy_api == "http://api/?a=1&b=2"


def test_autoload_without_env_file_is_noop(in_tmp_cwd):
    assert env.autoload() is None
    assert env.loaded_path() is None
    assert env.search_paths() == [Path.cwd() / ".env"]


def test_autoload_existing_variable_wins(in_tmp_cwd, monkeypatch):
    monkeypatch.setenv("EM_MAX_RETRIES", "7")
    _write(in_tmp_cwd, "EM_MAX_RETRIES=4\n")
    env.autoload()
    assert os.environ["EM_MAX_RETRIES"] == "7"


def test_autoload_is_idempotent(in_tmp_cwd):
    p = _write(in_tmp_cwd, "EM_ONCE=1\n")
    first = env.autoload()
    p.write_text("EM_ONCE=2\nEM_LATER=1\n", encoding="utf-8")
    assert env.autoload() == first
    assert os.environ["EM_ONCE"] == "1"
    assert "EM_LATER" not in os.environ


def test_env_file_var_points_to_another_file(in_tmp_cwd, monkeypatch):
    other = in_tmp_cwd / "conf" / "em.env"
    other.parent.mkdir()
    other.write_text("EM_FROM=explicit\n", encoding="utf-8")
    _write(in_tmp_cwd, "EM_FROM=cwd\n")
    monkeypatch.setenv("EM_ENV_FILE", str(other))
    assert env.autoload() == other
    assert os.environ["EM_FROM"] == "explicit"


@pytest.mark.parametrize("value", ["none", "NONE", " off ", "0", "false", ""])
def test_env_file_var_can_disable_autoload(in_tmp_cwd, monkeypatch, value):
    _write(in_tmp_cwd, "EM_SHOULD_NOT_LOAD=1\n")
    monkeypatch.setenv("EM_ENV_FILE", value)
    assert env.search_paths() == []
    assert env.autoload() is None
    assert "EM_SHOULD_NOT_LOAD" not in os.environ


def test_env_file_var_missing_file_warns_and_does_not_fall_back(in_tmp_cwd, monkeypatch, caplog):
    # 指了路径就只认那个文件：悄悄回退到运行目录会让人以为自己指定的配置生效了
    _write(in_tmp_cwd, "EM_SHOULD_NOT_LOAD=1\n")
    monkeypatch.setenv("EM_ENV_FILE", str(in_tmp_cwd / "nope.env"))
    with caplog.at_level("WARNING", logger="em.core.env"):
        assert env.autoload() is None
    assert "不存在" in caplog.text
    assert "nope.env" in caplog.text
    assert "EM_SHOULD_NOT_LOAD" not in os.environ


def test_autoload_falls_back_to_checkout_root(tmp_path, monkeypatch, clean_em_env):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".env").write_text("EM_FROM=root\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(env, "_checkout_root", lambda: root)
    assert env.autoload() == root / ".env"
    assert os.environ["EM_FROM"] == "root"


def test_autoload_cwd_wins_over_checkout_root(tmp_path, monkeypatch, clean_em_env):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".env").write_text("EM_FROM=root\n", encoding="utf-8")
    cwd = tmp_path / "work"
    cwd.mkdir()
    (cwd / ".env").write_text("EM_FROM=cwd\n", encoding="utf-8")
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(env, "_checkout_root", lambda: root)
    env.autoload()
    assert os.environ["EM_FROM"] == "cwd"


def test_autoload_never_raises_on_unreadable_file(in_tmp_cwd, monkeypatch, caplog):
    # import em 时调用：配置文件读不了只能告警，不能让导入失败
    _write(in_tmp_cwd, "EM_X=1\n")

    def boom(_path):
        raise PermissionError("denied")

    monkeypatch.setattr(env, "_read", boom)
    with caplog.at_level("WARNING", logger="em.core.env"):
        assert env.autoload() is None
    assert "denied" in caplog.text
    assert env.loaded_path() is None  # 读失败不能留下"已加载"的假状态


def test_checkout_root_is_this_repo_when_running_from_source():
    assert env._checkout_root() == ROOT


def test_template_is_available_from_the_package():
    text = env.template_text()
    assert "EM_PROXY_API=" in text
    assert "EM_PROXY_NUM=" in text
    assert "YOUR_UID" in text  # 只含占位符，不含真实凭证


# --- import em 本身就会加载：开新进程验证包入口的接线，而不只是 autoload 这个函数 ---


def _import_em_and_report(cwd: Path, **extra: str) -> list[str]:
    code = (
        "import os\n"
        "import em\n"
        "from em.core.settings import Settings\n"
        "s = Settings.from_env()\n"
        "print(s.proxy_api)\n"
        "print(s.proxy_num)\n"
        "print(os.environ.get('OTHER_PROJECT_KEY_7F3A'))\n"
    )
    child_env = {k: v for k, v in os.environ.items() if not k.startswith("EM_")}
    child_env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(ROOT / "src"), child_env.get("PYTHONPATH", "")) if p
    )
    child_env.update(extra)
    done = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.splitlines()


_DOTENV = "EM_PROXY_API=http://proxy-source.invalid/get?num=5&time=30\nEM_PROXY_NUM=5\nOTHER_PROJECT_KEY_7F3A=secret\n"


def test_import_em_picks_up_env_in_cwd(tmp_path):
    _write(tmp_path, _DOTENV)
    api, num, other = _import_em_and_report(tmp_path)
    assert api == "http://proxy-source.invalid/get?num=5&time=30"
    assert num == "5"
    assert other == "None"  # 别的项目的变量不注入


def test_import_em_keeps_variables_already_set(tmp_path):
    _write(tmp_path, _DOTENV)
    _api, num, _other = _import_em_and_report(tmp_path, EM_PROXY_NUM="9")
    assert num == "9"


def test_import_em_respects_env_file_none(tmp_path):
    _write(tmp_path, _DOTENV)
    api, num, _other = _import_em_and_report(tmp_path, EM_ENV_FILE="none")
    assert api == ""
    assert num == "1"
