"""取数失败时的处置建议：出口疑似被封、而代理又用不上时，告诉使用者该配什么。

库调用（传输层重试耗尽时挂到异常上）与命令行共用这一份文案，两边看到的内容一致。
"""

from em.core import env
from em.core.errors import EmptyResponseError, HttpStatusError, NetworkError
from em.core.settings import Settings

# 模板里的占位符（YOUR_UID / YOUR_VKEY）：生成 .env 之后没改就是这个样子
_PLACEHOLDER = "YOUR_"
# 代理源的最少配置：地址 + 每批数量。数量默认 1，接口一次返回多个时不改就是付了钱没用上
_REQUIRED = (
    "     EM_PROXY_API=<代理提取接口的地址，需返回纯文本，每行一个 ip:port>",
    "     EM_PROXY_NUM=<该接口每次返回的 IP 数>",
)


def is_egress_failure(exc: BaseException) -> bool:
    """是否为出口不通 / 被封一类的失败：连接断开、超时、空响应、403/429。"""
    if isinstance(exc, (NetworkError, EmptyResponseError)):
        return True
    return isinstance(exc, HttpStatusError) and exc.status_code in (403, 429)


def _proxy_gap(settings: Settings) -> str | None:
    """代理用不上的原因：``disabled`` / ``missing`` / ``placeholder``；能用时返回 None。"""
    if not settings.proxy_enabled or settings.proxy_mode == "never":
        return "disabled"
    sources = [s for s in (settings.proxy_api or "").split(",") if s.strip()]
    if not sources:
        return "missing"
    if all(_PLACEHOLDER in s for s in sources):
        return "placeholder"
    return None


def _env_file_status() -> str:
    """说清 .env 的现状：已加载哪个文件、没找到时找过哪里、或是被关掉了。"""
    loaded = env.loaded_path()
    if loaded is not None:
        if env.loaded_keys() == 0:
            return f"已读取 {loaded}，但其中没有 EM_ 开头的配置项。"
        return f"当前已加载：{loaded}。"
    paths = env.search_paths()
    if not paths:
        return f"注意：{env.ENV_FILE_VAR} 关闭了 .env 自动加载，目前只认环境变量。"
    looked = "、".join(str(p) for p in paths)
    return f"当前未找到 .env（查找位置：{looked}）。"


def egress_hint(exc: BaseException, settings: Settings, host: str = "") -> str | None:
    """出口类失败且代理用不上时返回一段多行提示；其余情况返回 None。

    代理配好了仍然失败（例如代理全死）不在此列：那不是"缺配置"能解释的。
    """
    if not is_egress_failure(exc):
        return None
    if settings.fixed_proxy:
        return "固定代理请求失败；请检查代理服务、认证和上游限制。此配置不会自动更换 IP 或采购动态代理。"
    gap = _proxy_gap(settings)
    if gap is None:
        return None
    target = f"对 {host} 的请求" if host else "请求"
    # 只有"没有源 / 被关闭"能确定全程直连；占位符源仍会被拿去回源，不能断言走的是直连
    how = "重试后仍然失败" if gap == "placeholder" else "全部走直连且都失败了"
    lines = [f"💡 {target}{how}：本机出口 IP 可能已被东方财富封禁（也可能只是网络不通）。"]
    if gap == "disabled":
        lines += [
            "   代理当前是关闭的（EM_PROXY_ENABLED=0 或 EM_PROXY_MODE=never），不会自动换 IP。",
            "   需要时改为 EM_PROXY_ENABLED=1、EM_PROXY_MODE=auto，并配置代理源：",
            *_REQUIRED,
        ]
    elif gap == "missing":
        lines += [
            "   还没有配置代理源，所以没法自动换 IP。配好下面两项后，直连失败时会自动切到代理：",
            *_REQUIRED,
            "   写进运行目录下的 .env（emshare --init-env 可生成带注释的模板），或直接设成环境变量；",
            "   import em 与 emshare 命令都会自动读取运行目录下的 .env。",
        ]
    else:
        lines += [
            "   EM_PROXY_API 还是模板里的占位符（YOUR_UID / YOUR_VKEY），代理用不上。请改成真实值：",
            *_REQUIRED,
        ]
    lines.append(f"   {_env_file_status()}修改 .env 后需重启进程（Notebook 重启内核）才生效。")
    return "\n".join(lines)
