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
- `import em` 与命令行都会自动读取运行目录下的 `.env`，只取 `EM_` 开头的变量，已设置的环境变量优先；`EM_ENV_FILE` 可指定路径或设为 `none` 关闭。装进 site-packages 后不再去包的上级目录找 `.env`。
- `emshare --init-env` 在当前目录生成带注释的 `.env` 模板（模板随 wheel 分发，已存在则不覆盖）。
- 没配代理源而直连全部失败时，异常信息与命令行输出会写明出口可能被封以及最少要配的 `EM_PROXY_API` / `EM_PROXY_NUM`。
