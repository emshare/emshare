"""默认值单一来源：渠道无关的兜底常量。"""

DEFAULT_TIMEOUT_SEC = 15
DEFAULT_CONNECT_TIMEOUT_SEC = 3
DEFAULT_MAX_RETRIES = 10
DEFAULT_BACKOFF_SEC = 0.2
DEFAULT_BACKOFF_CAP_SEC = 2.0
# 重试退避随机抖动：多 worker 同刻失败同刻重试会形成惊群，抖动错峰
DEFAULT_BACKOFF_JITTER_SEC = 0.1
DEFAULT_PROXY_API = ""

# 动态读超时（P95 滑动窗口）：按直连/代理分桶统计最近成功请求耗时，
# 读超时 = clamp(P95 × 倍数, 下限, 静态配置)。失败尝试不入窗，避免慢请求拉高 P95 的正反馈。
DEFAULT_REQUEST_DYNAMIC_TIMEOUT = True
DYNAMIC_TIMEOUT_WINDOW = 20        # 滑动窗口样本数（最近 N 次成功请求）
DYNAMIC_TIMEOUT_MIN_SAMPLES = 5    # 冷启动最少样本，不足时退静态超时
DYNAMIC_TIMEOUT_FACTOR = 3.0       # P95 倍数余量
DYNAMIC_TIMEOUT_FLOOR_SEC = 0.5    # 下限：防止正常波动被误杀

# 渠道级默认值：疑似出口被封的状态码
DEFAULT_ACTIVATE_STATUS = (403, 429)
