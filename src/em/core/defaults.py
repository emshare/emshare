"""默认值单一来源：渠道无关的兜底常量。"""

DEFAULT_TIMEOUT_SEC = 15
DEFAULT_CONNECT_TIMEOUT_SEC = 3
DEFAULT_MAX_RETRIES = 10
DEFAULT_BACKOFF_SEC = 0.2
DEFAULT_BACKOFF_CAP_SEC = 2.0
# 重试退避随机抖动：多 worker 同刻失败同刻重试会形成惊群，抖动错峰
DEFAULT_BACKOFF_JITTER_SEC = 0.1
DEFAULT_PROXY_API = ""

# 回源预筛：进池前并发探测批次 IP（应用层注入探测目标），判死的记黑名单不进池。
# 实测死 IP 率时段性 0%~82%，死 IP 高发时段可省约一半业务重试成本
DEFAULT_PROXY_PREFILTER = True

# 动态读超时（P95 滑动窗口）：按直连/代理分桶统计最近成功请求耗时，
# 读超时 = clamp(P95 × 倍数, 下限, 静态配置)。失败尝试不入窗，避免慢请求拉高 P95 的正反馈。
DEFAULT_REQUEST_DYNAMIC_TIMEOUT = True
DYNAMIC_TIMEOUT_WINDOW = 20  # 滑动窗口样本数（最近 N 次成功请求）
DYNAMIC_TIMEOUT_MIN_SAMPLES = 5  # 冷启动最少样本，不足时退静态超时
DYNAMIC_TIMEOUT_FACTOR = 3.0  # P95 倍数余量
# 下限：p95×3 会被快窗口压得过低（实测代理整页均值 0.79~1.25s），
# 0.5s 的下限等于把正常页判成超时，因此抬到覆盖均值的量级
DYNAMIC_TIMEOUT_FLOOR_SEC = 1.5

# 代理 IP 首次业务使用时的连接超时：未经业务验证的 IP 多卡在连接阶段，
# 收紧可快速判死（好 IP connect <0.5s，1.5s 有 3 倍余量不误杀）
FIRST_USE_CONNECT_TIMEOUT_SEC = 1.5

# 渠道级默认值：疑似出口被封的状态码
DEFAULT_ACTIVATE_STATUS = (403, 429)
