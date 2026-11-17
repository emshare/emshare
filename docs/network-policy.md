# 网络入口与架构约束

所有内置 HTTP 会话都使用 `src/em/core/session.py` 的 `ExplicitProxySession`。其 `trust_env=False` 禁止继承环境/系统代理和隐式 netrc 认证；每次请求仍按 `REQUESTS_CA_BUNDLE`、`CURL_CA_BUNDLE` 的顺序读取环境 CA。默认开启 TLS 校验，重定向不得重新注入环境代理。

## 允许的请求路径

| 用途 | 会话来源 | 唯一允许的底层发送函数 | 出口策略 |
| --- | --- | --- | --- |
| 行情、历史数据、报表等业务取数 | `application/market_data.py::_create_client` 创建并注入 | `core/transport.py::HttpClient._attempt` | 动态 `ProxyRouter` 或固定 `FixedProxyRouter` 决定出口；经过重试、预算和统计 |
| 代理供应商提取 | 与业务客户端共享受控会话，但不经过业务路由 | `core/proxy.py::fetch_proxies` | 直连，不依赖待采购的代理 |
| 代理预筛 | `_create_client` 向 `_make_prober` 注入同一会话 | `application/market_data.py::_make_prober.probe` | 使用待验证的显式代理，不得经过自动路由重新选出口 |
| 名称搜索（无动态代理源、代理关闭或 never） | `application/resolve.py::_session` 创建并缓存独立会话 | `application/resolve.py::_search` | 默认直连；设置固定代理后使用固定出口 |
| 名称搜索（配置了动态代理源） | 复用业务客户端（`_create_client`） | `core/transport.py::HttpClient._attempt` | 与业务取数同一路由：auto 先直连，被封或直连失败切代理并自动探测回直连；always 全程代理 |

固定代理直接复用业务传输入口和名称搜索入口，不增加会话创建点或底层发送函数。固定路由不构造代理池；供应商提取继续保持直连。

表中路径均相对 `src/em/`。会话只允许在表中的三个函数创建；业务渠道通过 `HttpClient.get_text` 获取响应，不能访问 `client._session` 或自己发请求。

上述例外为保持采购、探测和搜索各自明确的策略，不是整个文件的网络调用豁免。新增发送函数需要同步边界清单、本文档及最终发送参数的离线回归。

`ExplicitProxySession` 默认安装受控 `BoundedProxyAdapter`，业务客户端继续按自己的连接池大小装配该适配器。适配器为每个 manager 使用独立的 HTTP(S) 连接池映射，通过 urllib3 2.x 连接扩展记录 TCP、CONNECT、代理 TLS、目标 TLS、请求发送和响应头读取的失败阶段；非流式响应体错误在适配器消费响应时标记。不修改 urllib3 全局类或方法，不解析异常文本或凭耗时猜测阶段。当前内置发送路径均为非流式，外部自定义流式消费不保证响应体阶段标记。

`network_phase` 只用于当前请求的失败分类，原始异常类型仍保留。外部替身/自定义适配器没有阶段证据时标为 unknown，不能仅凭 ReadTimeout 进入软重试。TCP/CONNECT/TLS/发送阶段失败走连接故障策略，只有响应头或响应体读取超时允许同代理身份重试一次。阶段记录不调整连接/读取超时、TTL 或 deadline，也不证明历史真网失败的具体阶段。

关闭客户端与淘汰空闲代理管理器时显式关闭其连接池，池中空闲连接立即释放；在途连接归还到已关闭池时释放。保留在读取响应体期间保护活跃代理管理器的既有策略。

## 检查机制

- **Ruff TID251**：禁止 `requests.get/post/request/...`、原始 `requests.Session/session`（含子模块路径），以及常见旁路 HTTP 客户端。只有 `ExplicitProxySession` 继承行有精确的 `noqa`；没有生产文件级豁免。测试文件允许构造底层会话和替身。
- **架构守卫**：`tests/guards/test_network_boundaries.py` 按文件与函数限定创建和发送点，检查常规导入、别名、简单赋值、会话参数、`client._session` 访问及 `trust_env` 修改；禁止业务模块导入底层网络实现和新增 pandas 文件读取入口，避免隐式 URL 下载。它还通过项目的真实 Ruff 配置运行反例，保证 TID251 确实启用。
- **行为回归**：`tests/unit/test_network_policy.py` 在真实 requests 参数合并与重定向逻辑之后拦截适配器，验证五类路径实际使用的代理、CA 参数和默认 TLS 校验。静态规则不能替代这些检查。

检查命令（安装项目 dev 依赖后）：

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/guards tests/unit/test_network_policy.py
```

架构守卫是常规 Python 代码的静态回归，不是动态执行的安全沙箱。反射、复杂对象流、动态加载或未来引入的新网络库仍需要代码审查；不能据此宣称任意绕过都能被识别。未来若需 pandas 解析下载文件，应先明确离线解析入口，禁止直接把远端 URL 交给 pandas。
