# AKShare 代理链路深入分析与 emshare 建议

核查日期：2026-11-16。通过 `git ls-remote` 核对 AKShare HEAD 为 `25acdfac7ddf3a0721a0ebdcc6a1d7ef3e76abc9`，提交时间为 2026-11-15 21:58:12 +08:00，与本次分析的浅克隆一致。

结论：AKShare 提供的是统一网络配置和请求封装，未在其核心代理链路中实现 emshare 式动态代理池。可借鉴统一入口的工程约束、显式配置和有条件停止重试；不宜移植全局可变状态、统一长退避或每次重建会话的策略。

## 1. 实际调用链

以 `stock_zh_a_spot_em()` 为例：

```text
stock/quote/stock_hist_em.py:stock_zh_a_spot_em
  → utils/func.py:fetch_paginated_data
      → _get_page
          → utils/http.py:request_with_retry(fresh_session=True)
              → http.Session.request
                  → _apply_defaults(timeout, proxies)
                      → requests.Session.request
                          → merge_environment_settings
                              → Session.send → HTTPAdapter → 代理/目标服务器
```

- 第一页决定总页数，随后串行翻页，每页前随机等待 0.5～1.5 秒。这是该分页帮助函数的行为，不是所有接口统一限速。
- `utils/context.py` 的全局单例保存 `proxies` 与 `timeout`；请求时读取，既有 Session 也能读取新配置。
- `set_proxies` 不采购 IP、不检测代理存活、不自动轮换，也不复制或校验传入字典。`get_proxies` 返回原对象。
- `ProxyContext` 只保存旧值、替换全局值、退出时恢复。普通嵌套按相反顺序退出可以工作，但不同任务交错进入退出没有隔离。
- 有些数据接口直接使用 `http.get`；它不会自动套用 `request_with_retry`。

源码定位：AKShare `akshare/utils/context.py:13`、`akshare/utils/http.py:100`、`akshare/utils/func.py:19`、`akshare/stock/quote/stock_hist_em.py:15`。

## 2. 代理参数不是简单的单一优先级

以下为普通 requests 后端、本次环境 requests 2.34.2 的离线验证。假设全局代理为 A，环境 HTTPS 代理为 E：

| 调用 | HTTPS 最终代理 | 原因 |
|---|---|---|
| `http.get(url)` | A | 缺少参数，`setdefault` 注入全局配置 |
| `http.get(url, proxies=B)` | B | 显式参数保留；相同键不被环境覆盖 |
| `http.get(url, proxies=None)` | E | 参数存在，跳过全局默认；底层继续读环境 |
| `http.get(url, proxies={})` | E | 空字典不代表禁止环境代理 |
| `make_request_with_retry_json(url, proxies=None)` | A | 兼容封装主动省略 None，重新采用全局配置 |
| 未设全局代理，仅 `session.proxies=A` | E | requests 在合并 Session 配置前先加入环境代理 |

这是按代理键合并的结果；只有 HTTP 的配置不能理解为覆盖 HTTPS，host 专用代理键与 `all` 也有各自选择规则。

**可变字典副作用：** 全局配置仅含 `http` 时，requests 会把环境 `https` 用 `setdefault` 写入同一个非空字典。随后即使环境 HTTPS 代理变化，字典里旧值仍优先。本次实验同时验证调用方原字典被修改、第二次请求继续使用旧环境值。

**并发上下文副作用：** A 进入、B 进入、A 退出、B 退出：A 请求可能使用 B 的代理；A 退出将全局值恢复为空；B 最后退出反而恢复 A，未回到初始值。通过确定性交错调用验证，无需依靠线程调度偶然触发。

对 emshare 的启示：采用客户端级不可变配置，在请求边界生成新字典。若增加临时上下文，需要任务隔离，并明确线程池的上下文传播；不能只照搬这个全局上下文管理器。

## 3. 重试、新连接与换 IP 是三件事

`http.request_with_retry`：

- 默认 `max_retries=3` 指总尝试数；emshare 同名配置表示额外重试数，默认 10，对应最多 11 次尝试。
- 重试连接错误、超时、传输中断，以及 429、500、502、503、504。普通 403 不在其重试状态集合。
- 等待公式为 `base_delay * 2**attempt + uniform(0, base_delay)`。
- 可选 `retry_if(response)` 识别 HTTP 200 的错误内容。
- 重试用尽后，异常路径抛最后异常；错误响应路径返回最后响应，甚至 `retry_if` 仍判定失败的 200 也可能返回。调用方仍需检查。兼容封装和 `_get_page` 又做了状态码检查。
- 未传代理参数时，每轮仍读取全局配置；如果其他代码修改全局值，重试出口可能随之改变，但这不是自动代理轮换机制。

**`fresh_session=False` 也不等于跨尝试复用 Session。** 此路径调用 `requests.request`，后者每次创建并关闭 Session；True 路径则显式创建其 Session 子类并挂载小连接池。实验中，两条路径各发生 3 次尝试，均产生 3 个不同 Session，使用同一代理地址。代理服务是否自行轮换公网出口不由这段代码决定。

emshare 已有复用连接和有界代理连接管理器。不能因为 AKShare 使用 `fresh_session=True` 就推断 emshare 应全量关闭复用；如怀疑坏连接，需要先对特定异常做有界、可比较的重建实验。

源码定位：AKShare `akshare/utils/http.py:184`、`akshare/request.py:11`；本地 requests `requests/api.py:24`。emshare `src/em/core/transport.py:118`、`src/em/core/session.py:10`。

## 4. push2 断连识别的价值与边界

AKShare 对指定 push2 系主机检查异常链中的 `RemoteDisconnected`、`ConnectionResetError`，同时遍历 `args`、`__cause__`、`__context__`，并用 visited 集合防循环。匹配后抛 `Push2RateLimitError`，重试循环立即结束。

这里没有持久冷却状态、出口级失败历史或自动替换 IP；用户再次调用仍会发请求。源码里的“5 分钟”“40 分钟”是维护者观察和提示文案，不能作为我们环境的固定恢复时间。

**误判边界已复现：** 构造含 `RemoteDisconnected` 的 `ProxyError`，请求目标为 push2，同样被判为 `Push2RateLimitError`，只尝试一次。它没有先证明断连来自目标站而非代理连接。因此可以借鉴异常链遍历，但错误应保留“疑似限流/远端断连”的不确定性。

建议 emshare 根据出口是否真正可更换决定动作：

- 直连、没有代理源，或固定代理且不能切出口：少量重试后快速失败或进入可配置冷却，避免每次业务调用又重复打同一出口。
- 动态代理路径：保留失败分级和受预算约束的换出口能力；不要一律遇到 push2 断连就终止整个任务。
- 域名识别属于东财渠道知识，适合通过渠道策略注入，避免把东财域名判断硬编码进通用 core。

另一个小型健壮性差异：emshare `_classify` 当前遍历 args 和 cause，不遍历 context。仅把 ReadTimeout 包在 context 的构造场景被分成硬连接错误；这证明覆盖缺口，但不代表已测得真实线上发生率。

源码定位：AKShare `akshare/utils/http.py:73`；emshare `src/em/core/transport.py:40`、`src/em/core/resilience.py:28`。

## 5. 对 emshare 最直接的发现

### P1：让路由决策与实际发送一致

`_create_client` 创建的 requests Session 默认 `trust_env=True`；业务直连路径传 `proxies=None`。离线拦截真实 Session.send 验证，`proxy_mode='never'` 仍使用模拟的环境 HTTPS 代理。

影响包括：

- 直连成功率、耗时和“本机出口”错误提示可能实际对应环境代理。
- auto 的直连恢复探测可能探测的是环境代理。
- 代理供应商提取请求没有独立禁用环境代理，也会受其影响。
- 动态代理分支显式给出的 http/https 值，在相同键的合并中仍优先；不能夸大成“所有动态代理都会被环境覆盖”。

建议显式区分继承系统代理、真正直连、固定代理和动态代理。供应商请求应有独立网络策略，默认保持不依赖业务动态代理，以免采购链路循环依赖。若用 `trust_env=False` 实现真正直连，需同步处理它对环境 CA 证书、netrc 的影响；不能把 `proxies={}` 当作修复。

相关代码：`src/em/application/market_data.py:226`、`src/em/core/transport.py:340`、`src/em/core/proxy.py:107`、`src/em/application/resolve.py:43`。余额查询已有独立 `trust_env=False`，可参考其显式控制方式，但不意味着所有网络路径都已隔离。

### P1：无可切换出口时，重试策略应收敛

在未配置代理源、auto、默认重试数、持续 push2 断连的离线场景中，emshare 发出 11 次 HTTP 尝试、等待 10 次。实验将 sleep 替换为记录，未发真实请求。该结论针对一次传输层调用；外层时间预算可能提前终止，页级重试也可能再次发起调用。

当前短退避注释基于“换的是新 IP”，但相同逻辑也被用在无法换 IP 时。建议将实际路由能力纳入重试决策，并让外层页级重试尊重冷却结果，避免只减少内层次数却仍被外层重复调用。

### P2：统一网络入口的可执行约束

AKShare 通过 Ruff TID251 禁止业务模块直接构造 requests/curl 请求，下载文件也经 `get_buffer` 转成内存流交给 pandas。它同时测试最终送达 Session.send 的参数，避免“配置已赋值”却未实际生效。

emshare 可借鉴这一约束方式，但需要区分：业务请求、代理供应商提取、预筛、余额查询、名称搜索。它们应共享明确的网络配置规则，未必全部进入会触发代理采购的业务路由。名称搜索目前使用独立 Session；新增固定代理入口时尤其要明确它是否覆盖该路径。

Ruff 规则并非万能：新库、pandas 直接读 URL、间接包装仍需审查与最终发送参数测试。

### P2：固定代理的便利入口

按需增加客户端/Settings 级固定代理，适用于本地代理或企业出口；不把固定代理硬塞进短效 TTL 池，也不把“代理提取 API URL”和“代理服务器地址”混为一个配置。

建议明确冲突处理与优先级、异常分类、来源统计和凭证脱敏；固定代理模式也不应隐式采购动态 IP。以上为建议设计，尚未实施。

### P3：按目标与出口节流的实验

AKShare 的串行分页加随机间隔提示了“降低请求频率”这条路线。emshare 现有最少在飞分配与 worker 收敛主要约束并发，不能等价于请求速率限制。

可在目标主机 + 出口维度做可选速率控制实验，比较成功页数/出口、失败率、采购量和总耗时。不要全量照搬每页等待 0.5～1.5 秒：它会消耗短效代理租期；也不应未经实测就合并所有东财子域的限流状态。

## 6. 应保留的现有能力

emshare 已有 TTL/剩余租期准入、后台续期、最少在飞分配、采购单飞、多源故障转移、预筛、软失败同 IP 重试、失败淘汰、host 路由状态机、预算控制与用量记录。AKShare 的核心封装未提供对应替代实现。

curl_cffi 是 AKShare 另一条 HTTP 后端，用于部分接口的浏览器指纹兼容，并非代理池；其封装没有套用 requests 路径同样的 push2 异常识别或该重试函数。配置统一不等于两条后端的异常、超时和重试语义统一。目前没有本次实验依据支持为 emshare 全面引入它。

还有一个独立边界：requests 的读取超时不是整个响应的总耗时上限。emshare 在请求前后检查 deadline、压缩连接/读取超时，不能据此宣称能在任意持续分块传输下硬中断在途请求。此次没有做慢速流实验，不把这一静态语义判断当作线上已发生故障。

## 7. 验证范围与产物

- 12 个离线断言场景全部通过，使用 AKShare 实际 context/http/request 源文件及本地 requests 2.34.2。
- 用导入桩跳过 AKShare 包级依赖和未使用的 curl 后端；没有执行真实 curl_cffi，不是 AKShare 全量测试。
- 在 requests.Session.send 拦截发送，网络请求数为零，没有提取或消耗供应商 IP，没有测真实性能、封禁周期或可用率。
- 实验脚本：`.arts/akshare-proxy-review/probe.py`；详细结果：`.arts/akshare-proxy-review/results.json`。AKShare 源码快照位于 `/tmp/akshare-proxy-review-20261116`，重跑需要保留该目录。
- 本次仅新增分析报告和本地实验产物，没有修改 emshare 产品代码。

建议实施顺序：先明确出口语义并消除环境代理歧义，再收敛不能换出口的重试，随后增加统一网络入口约束；固定代理和出口节流按需求推进。
