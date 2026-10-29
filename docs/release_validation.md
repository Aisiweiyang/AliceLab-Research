# 初始开源版本地验证

验证日期：2026-10-29。版本：0.1.0。

在全新 Python 3.13.0 虚拟环境中执行 editable 安装（含开发依赖），未使用原工作区的 site-packages。

- NumPy 2.5.4、pandas 3.1.0、SciPy 1.18.1、pytest 9.2.0。
- `python -m pytest -q`：16 项通过，包含原离线检测器整套回归脚本。
- `python -m alicelab demo --out ...`：三类配方全部真实运行，生成合成输入、CSV/JSON 结果和 manifest。
- `python -m pip check`：未发现依赖冲突。
- 源码包与 wheel 构建成功；wheel 独立安装后运行三类合成演示成功；源码包包含模板、使用说明与原检测器回归脚本。
- 发布文件检查：不包含个人绝对路径、凭据、原行情数据、第三方网页快照或旧 Git 历史。

这份记录是本地检查结果。GitHub Actions 会另行在 Python 3.11/3.13 上执行测试、合成演示和打包；其实际状态以仓库 Actions 为准。以上不是原论文实证结果或策略有效性的验证。
