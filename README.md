# AliceLab-Research

作者：[Aisiweiyang](https://github.com/Aisiweiyang)

从 Alice 研究项目中整理出来的 Python 工具，主要用于因子诊断、事件研究和大模型价格分析。可以单独安装，不需要 Alice 量化系统的代码或数据库。

目前有三个研究模板：

- `factor_health`：分析因子 IC 等序列中可能的变化位置，计算离线变点后验；也提供 CUSUM 函数。
- `event_study`：用市场模型计算事件发生后的异常收益，比较不同持有窗口的累计异常收益。
- `capability_price`：比较模型的能力与价格，计算达标最低价、价格变化分解和质量调整后的参考价。

每次研究用一份 JSON 文件指定输入和参数。运行后保存结果、配置、随机种子、依赖版本和输入文件哈希，方便检查和重跑。

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

`demo` 会生成合成数据并运行三个模板，结果保存在 `outputs/demo`。再次运行时请换一个输出目录，程序不会覆盖已有结果。

## 使用自己的数据

在 `data/` 下放入自己的 CSV，然后修改 `templates/` 中对应的 JSON 文件，填写研究假设、文件路径和参数。例如：

```powershell
.\.venv\Scripts\python.exe -m alicelab run --spec templates/factor_health.json --out outputs/my-first-study
```

CSV 字段和参数说明见[使用说明](docs/usage.md)。使用真实数据时，保留 `source_type: "user_supplied"`；日期、复权口径、数据在当时是否可得，以及来源许可，需要自行核实。

## 项目结构

```text
src/alicelab/     算法和命令行入口
templates/       研究配置示例
tests/           数值、输入检查和运行测试
docs/            使用说明、方法和代码来源
```

## 使用前了解

仓库不附带真实行情或模型报价。演示数据全部由固定种子生成，用来检查程序，不能作为市场表现、模型价格或论文结果引用。

变点检测使用整段序列，属于离线分析；事件研究不能单独证明新闻与股价变化之间的因果关系；价格分析要求数据采用相同的能力基准版本和币种。具体方法与限制见 [methods.md](docs/methods.md)。

本项目不连接券商，也不负责交易和账户核算。接入 Alice 或其他量化平台时，需要自行导出数据或编写适配器。

当前为 0.1.0 版，后续不定期更新。欢迎通过 Issue 报告问题或讨论改进。

代码与原创文档采用 [MIT License](LICENSE)。代码来源见 [source_provenance.json](docs/source_provenance.json)，自行取得的数据仍适用原来源的条款。
