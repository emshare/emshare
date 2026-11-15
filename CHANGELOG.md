# 更新日志

版本号遵循语义化版本。PyPI 发行名为 `emshare`，导入名为 `em`。

## [0.1.0] - 2026-11-14

### 新增

- 首次发布：东方财富行情接口（板块 / 全市场 / K 线 / 分时 / 资金流 / 龙虎榜 / 大宗交易 / 财报等），返回领域模型。
- 可选 pandas 支持：`pip install "emshare[pandas]"` 后可用 `df_*_em` 系列。
- 动态代理池：多源冗余、预筛、连败熔断、TTL 续期、采购账本。
- 命令行入口 `emshare`（等价 `python -m em`）。
- 类型标注随包分发（`py.typed`），支持 `em.__version__`。

### 说明

- 采购账本默认写到 `$XDG_DATA_HOME/emshare/ledger.jsonl`，不再写入当前目录；`EM_LEDGER_PATH` 可改路径或设为 `none` 关闭。
- `import em` 不再自动加载 `.env`；只有 CLI 入口会读取当前目录的 `.env`。
