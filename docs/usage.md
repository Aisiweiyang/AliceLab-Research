# 使用说明

## 运行约定

安装后可用 `python -m alicelab` 或 `alicelab`。`run --spec ... --out ...` 会执行指定配方；相对输入路径以 JSON 所在目录为基准。输出目录必须尚不存在。

配方必填字段为 `schema_version`（当前为 1）、`recipe`、`hypothesis`、`source_type`、`seed`、`inputs`、`parameters`。`source_type` 只接受 `synthetic`、`user_supplied`；它是用户声明，并非来源认证。模板不能自动将数据升级为官方或已核验。

所有结果目录保存实际 spec、输入文件与 spec 的完整 SHA-256、参数、随机种子、运行时间和依赖版本。manifest 默认只记录输入文件名，不泄露本机绝对路径；完整原始输入应由研究者另外保存。结果中的 `spec.json` 是记录副本，重新运行时应使用原位置的 spec，或修正相对路径。

## 因子健康度

`inputs.series` CSV 至少有数值列 `ic`。每行代表一个观测周期，不能有 NaN、无穷大；程序不补齐交易日、不计算原始股票因子 IC。调用者应保证序列顺序和频率一致。

参数：`column`、`min_seg`、`lam`、`k_max`、`standardize`。建议显式保留模板中的 `standardize: true`，因为 NIG 先验依赖序列尺度。样本数必须大于两倍最短分段长度。

输出：`location_posterior.csv`、`result.json`。位置为从零开始的样本边界；位置后验条件为“恰好一个断点”，不能把最高点概率直接当作发生变化的概率。

## 事件研究

`inputs.firm` 和 `inputs.market` CSV 各需要 `date`、`adjclose` 或 `close`。有 `adjclose` 时优先使用该列。请自行确认复权含义和两个数据源的单位一致性。重复日期、非正价格、缺失价格会被拒绝。

先在各自日历计算收益，再对共同日期取交集。`event_date` 被映射到其后首个共同有收益的会话；结果同时保存请求日和反应日。程序不知道公告发布时间，盘后公告的首个反应日需由你确定。日历缺口不会自动修复。

参数：`event_date`、`estimation`（默认 230 个共同收益会话）、`gap`（默认空开 20 个会话）、`horizons`（默认 `[1,2,6]`）、`n_boot`（默认 4999）。估计样本不包含事件日和间隔区间。可用会话不足时明确失败，不缩短窗口。

输出 `event_results.csv`。CAR 为小数收益之和，例如 0.01 代表 1%；`empirical_p` 为以估计窗残差构造的双侧经验尾部概率，并非因果效应的显著性证明。

## 大模型能力与价格

`inputs.panel` CSV 需要：

| 字段 | 含义 |
|---|---|
| month | `YYYY-MM` |
| model | 稳定的模型身份；每个模型每月只能有一行 |
| price | 正数价格；所有行使用相同单位和计价口径 |
| capability | 正数能力分数；仅可比基准可合并 |
| benchmark_version | 单一版本标识 |
| currency | 单一币种标识 |

程序拒绝混合基准版本、混合币种和重复模型—月份。它不验证供应商报价、不查询实时价格、不验证基准分数是否实测；请在研究资料中保留这些证据。

参数：`thresholds`、`reference`、`min_models`。输出达标价、构成分解、hedonic 参考价和最新月帕累托前沿。达标模型为空时保留该月的空价格，不能用零价代替。分解中无共同存活模型时 within 与 residual 为缺失。

API 另提供 `link_factor`：仅正数、有限、两版均标为实测的重叠模型计入链接样本。`weak_link` 是信息不足标记；当前 CLI 不自动拼接基准版本。
