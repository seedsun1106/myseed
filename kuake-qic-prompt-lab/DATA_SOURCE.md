# 数据来源与授权说明

## 基准来源
本实验数据来自 **CBLUE 中文医疗信息处理评测基准** 的 **KUAKE-QIC（医疗搜索意图分类）** 子任务：

- 天池 CBLUE 官方页面（数据集发布与授权入口）
- Gitee 官方仓库：`gitee.com/CBLUEBenchmark/CBLUE`

KUAKE-QIC 官方 dev 集（`dev.txt`，1955 行 `query<Tab>官方标签`，取自 PaddleNLP 数据集镜像）仅用于核对样本的官方标签，不随本仓库分发。

## 版权与使用范围
- 数据版权归 CBLUE / KUAKE-QIC 原发布方所有；本仓库**不包含官方全量数据集**。
- 本仓库仅收录 **200 条样本**（开发集 150 条 + 黄金留出集 50 条），仅用于**研究、学习与作品集演示**。
- **禁止商业用途**，禁止将样本再分发为独立数据集；如需正式研究或商用，请到天池 CBLUE 官方渠道申请授权并引用原始基准。
- 仓库内代码按 MIT 许可证开源，代码许可不覆盖数据。

## 样本构成与可复现性
| 集合 | 规模 | id 前缀 | 文件 |
|---|---|---|---|
| 开发集（典型 90 + 边界 60） | 150 | `DT-` / `DB-` | `data/dev.csv` |
| 黄金留出集（调优期全程封存） | 50 | `HO-` | `data/holdout.csv` |

- 原始工作簿：`data/dataset.xlsx`（含 `export`、`黄金留出集` 等 sheet）。
- 抽样 **seed=42**，可复现；中文标签经固定 11 类映射表转为英文 code，映射表见 `src/export_holdout.py`。
- 留出集导出脚本：`src/export_holdout.py`，内含 50 行 / id 唯一 / 与开发集零重叠（id、query 精确、query strip 三种口径） / 与 dev.txt 金标准一致等核对。
- `data/dev.csv` 按同一做法自 `export` sheet 取 `DT-`/`DB-` 开头的 150 行导出，列同为 `id,input,expected`。
- 评测脚本 `src/eval_batch.py`；错题与宏平均 F1 分析 `src/analyze_exam.py`。
