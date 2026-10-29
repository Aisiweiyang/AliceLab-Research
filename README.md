# AliceLab Research

面向金融与 AI 经济研究的轻量 Python 工具箱。提供可执行研究模板、显式 CSV 输入、参数记录和 SHA-256 输入清单，可独立于 Alice 量化系统使用。

**这是初始开源版。演示数据全部由固定种子合成，不代表真实市场收益、当前模型价格或论文复现结果。** 本项目没有券商连接和自动交易功能。

## 可以做什么

| 研究模板 | 实际功能 | 结果边界 |
|---|---|---|
| `factor_health` | 单断点位置后验、截断多断点数后验；另提供双侧 CUSUM 函数 | 离线诊断；不能直接解释为在线报警或可盈利的仓位规则 |
| `event_study` | 市场模型、多个持有窗口 CAR、同窗口长度的经验尾部概率 | 描述性事件研究；不证明新闻的因果效应 |
| `capability_price` | 能力—价格前沿、达标最低价、匹配模型分解、hedonic 参考价 | 单一基准版本与币种；分解残差包含成员变化及权重变化 |

## 快速开始

需要 Python 3.11 或更新版本。Windows PowerShell：

```powershell
git clone https://github.com/Aisiweiyang/AliceLab-Research.git
cd AliceLab-Research
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alicelab demo --out outputs/demo
.\.venv\Scripts\python.exe -m pytest -q
```

Linux/macOS：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m alicelab demo --out outputs/demo
.venv/bin/python -m pytest -q
```

演示会真实执行三类模板，生成合成输入、结果 CSV、实验配置和 `manifest.json`。每次运行请使用新的输出目录，已有结果不会被覆盖。Python API、输入格式与模板用法见[使用说明](docs/usage.md)。

## 使用自己的数据

从 `templates/` 选择 JSON 配方，填写研究假设、数据相对路径和参数，设置 `source_type` 为 `user_supplied`，然后运行：

```powershell
.\.venv\Scripts\python.exe -m alicelab run --spec templates/factor_health.json --out outputs/my-first-study
```

模板默认指向 `data/` 中由你提供的 CSV；仓库不附带真实数据。输入字段、日期对齐、复权、时点可得性、样本选择和数据使用权限由研究者核实。未知参数会被拒绝，避免配置看似生效却被忽略。

## 项目结构

```text
src/alicelab/     核心算法、输入验证、实验执行器与 CLI
templates/       三类可编辑、可执行的研究配置
tests/           已知答案、原检测器回归、边界与完整运行测试
docs/            方法、使用说明、清理范围与来源记录
```

## 与 Alice 量化系统的关系

本项目由 AliceLab 私有研究工作区中可复用的研究工具整理而来，具有独立依赖和 Git 历史。它不包含旧 Alice v4/v5 框架、个人数据库、账户记录、历史网页快照或内部报告。

接入其他量化平台时，先导出具备明确版本的 CSV，再运行这里的模板。策略评分、交易模拟和账户核算由目标平台负责；本仓库尚未实现 Alice V8 的原生适配器。

## 验证和限制

- 测试覆盖算法已知答案、原检测器回归、无效输入、价格指数和事件窗口统计量，以及三类模板的完整运行。
- 方法与局限见 [methods.md](docs/methods.md)；原代码来源见 [source_provenance.json](docs/source_provenance.json)。
- 公开版不提供原内部研究的收益或模型价格结论，不宣称复现了原论文或完成独立实证验证。
- 后续按实际需求维护，暂无固定更新周期。

代码与本仓库原创文档采用 [MIT License](LICENSE)。自行取得的数据适用各自来源的条款。
