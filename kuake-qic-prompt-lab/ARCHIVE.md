本文档为迭代期快照，定版状态以 final_archive/final_manifest.json 为准

# 医疗搜索 Query 分类 · Prompt 调优实验归档（V0–V3.1）

> 归档对象：KUAKE-QIC 医疗搜索意图 11 分类的 5 版 system prompt 与逐轮评测结果。
> 迭代期：2026-11-05。单变量控制：每版只整体替换脚本内的 `PROMPT_V0` 常量并更换输出文件名，模型、参数、数据、解析、重试、断点续跑逻辑全部不动。
> 本文件记录 V3.1 跑完时的迭代期状态；最终定版状态见第 7 节与 `final_archive/`。

## 1. 实验概览与口径

- **数据**：CBLUE / KUAKE-QIC 官方 `dev.txt`（1955 行 `query<Tab>标签`）。开发集 150 条（id 前缀 `DT-` 90 / `DB-` 60；category `typical` 90 / `boundary` 60），黄金留出集 50 条（`HO-001`~`HO-050`）在调优全程封存，与开发集 id / query 零重叠。
- **标签**：中文标签映射为 11 个英文 code —— 治疗方案=method、病情诊断=diagnosis、疾病表述=disease_express、就医建议=advice、注意事项=attention、医疗费用=price、后果表述=result、指标解读=metric_explain、病因分析=cause、功效作用=effect、其他=other。
- **模型与调用**：`glm-5.3-flash`，`temperature=0.1`，`reasoning_effort="low"`（zhipuai SDK 无顶层该参数，经 `extra_body` 透传）。密钥只从环境变量 `ZHIPU_API_KEY` 读取，脚本内无明文。
- **解析与计分**：只接受 `{"label": "英文code"}` 形式的 JSON；解析失败或 label 不在 11 类内记 `FORMAT_ERROR`；`predicted` 与映射后的 `expected` 比对，`correct` 记 1/0。
- **执行**：每次调用间隔 0.6s、单条失败重试 2 次（间隔 3s）、每 10 条打印进度、支持 `--limit N`、按 `results_*.csv` 已有 id 断点续跑；结果 `utf-8-sig` 编码，`raw_response` 截 500 字符。
- **产物**：`results/results_v0.csv` ~ `results/results_v3_1.csv`、`results/results_holdout.csv`；五版全量均为 150 条真跑，无报错、无重试、`FORMAT_ERROR` 均为 0。
- **汇总口径**：总体 / typical / boundary / 各 expected 分组准确率；期末考另按固定 11 类 one-vs-rest 统计 P / R / F1 并取宏平均（分母为 0 记 0，含 F1=0 的类别，不加权不剔除）。


## 2. V0（单行，163 字符）

```text
你是分类器。将输入的医疗搜索query分为以下11类之一：method, diagnosis, disease_express, advice, attention, price, result, metric_explain, cause, effect, other。只输出JSON：{"label": "英文code"}
```

- **设计**：仅枚举 11 个英文 code，不给任何判定依据，作为空白基线。
- **结果**：总体 **35.33%（53/150）**；typical 36.67%（33/90）、boundary 33.33%（20/60）。
- **分组**：cause 7/7、price 6/6 满分；method 9/33（27.27%）、diagnosis 5/18（27.78%）、metric_explain 2/10（20%）、result 0/8（0%）、other 1/24（4.17%）。
- **诊断**：模型输出分布严重偏斜，预测 `advice` 40 次、`cause` 21 次、`effect` 18 次，而 `method` 只预测 15 次（实际期望 33 次）、`other` 仅 1 次（期望 24 次）。问题不在边界样本（typical 与 boundary 差距很小），而在 Prompt 根本没给分类依据。


## 3. V1（13 行，468 字符）

```text
你是医疗搜索query分类器。将输入的query分为以下11类之一。只输出JSON：{"label": "英文code"}
类别定义：
- method 治疗方案：询问怎么治疗、怎么处理、用什么药、做什么手术等具体做法
- diagnosis 病情诊断：描述自身症状后询问得了什么病、是不是某种病
- disease_express 疾病表述：询问某种疾病的症状、表现、能否治愈
- advice 就医建议：询问去哪里看病、挂什么科、哪家医院或医生好
- attention 注意事项：询问患病、用药或孕期等特殊时期能否做某事、有何禁忌
- price 医疗费用：询问治疗、检查、手术的花费
- result 后果表述：询问某种情况或行为会导致什么后果、危害、影响
- metric_explain 指标解读：询问化验、体检指标数值的含义、是否正常
- cause 病因分析：询问疾病或现象的成因
- effect 功效作用：询问某种药、食物、疗法的作用、效果、副作用
- other 其他：单纯陈述情况、意图不明、或以上类别都不适用时
```

- **改动**：在枚举之外补齐 11 类判定要点（首行 +「类别定义：」+ 11 条定义，共 13 行），输出 `results_v1.csv`。
- **结果**：总体 **70.00%（105/150）**，比 V0 **+34.67pct（多对 52 条）**；typical 68.89%、boundary 71.67%。
- **分组跃升**：result 0→75%、metric_explain 20→90%、method 27.27→81.82%、effect 45.45→100%、advice 54.55→100%、disease_express 60→80%。
- **代价**：price 100→83.33（少 1 条）。`other` 仍最弱 12.50%（3/24）——模型倾向把意图不明的 query 塞进具体类。
- **结论**：本轮是收益最大的一次干预，说明「给判定依据」远比「给标签名」重要。


## 4. V2（22 行，833 字符）

```text
你是医疗搜索query分类器。将输入的query分为以下11类之一。只输出JSON：{"label": "英文code"}
类别定义：
- method 治疗方案：询问怎么治疗、怎么处理、用什么药、做什么手术等具体做法
- diagnosis 病情诊断：描述自身症状后询问得了什么病、是不是某种病
- disease_express 疾病表述：询问某种疾病的症状、表现、能否治愈
- advice 就医建议：询问去哪里看病、挂什么科、哪家医院或医生好
- attention 注意事项：询问患病、用药或孕期等特殊时期能否做某事、有何禁忌
- price 医疗费用：询问治疗、检查、手术的花费
- result 后果表述：询问某种情况或行为会导致什么后果、危害、影响
- metric_explain 指标解读：询问化验、体检指标数值的含义、是否正常
- cause 病因分析：询问疾病或现象的成因
- effect 功效作用：询问某种药、食物、疗法的作用、效果、副作用
- other 其他：单纯陈述情况、意图不明、或以上类别都不适用时
判定示例：
query: 高血压是什么原因引起的 → {"label": "cause"}
query: 我最近总是头晕，晚上躺下更明显，这是怎么回事 → {"label": "diagnosis"}
query: 痔疮用什么药能治好 → {"label": "method"}
query: 痔疮去医院该挂哪个科 → {"label": "advice"}
query: 孕妇不小心吃了两片去痛片，对胎儿有没有影响 → {"label": "result"}
query: 长期吃板蓝根有什么副作用 → {"label": "effect"}
query: 去年做过阑尾炎手术，现在恢复得挺好的 → {"label": "other"}
query: 有没有宝妈家孩子也这样啊，来说说 → {"label": "other"}
```

- **改动**：在 V1 完整类别定义之后追加「判定示例」8 条（共 22 行），输出 `results_v2.csv`。
- **结果**：总体 **74.67%（112/150）**，比 V1 **+4.67pct（多对 7 条）**；typical 74.44%、boundary 75.00%。**五版最优，后续定版采用本版。**
- **V1→V2 翻转**：错变对 11 条、对变错 4 条、净 +7。示例主要把陈述句 / 闲聊拉回 `other`（DT-020、DT-029、DB-044、DB-059），把「描述症状求判断」从 `cause` 拉回 `diagnosis`（DT-034/035/038、DB-053）；退步 4 条为 DT-042、DT-079、DT-089、DB-015。
- **分组**：advice / effect / cause 100%，disease_express 90%，attention 83.33%，method / price 81.82% / 83.33%，`other` 29.17%（7/24）仍是最大短板。
- **期末考（V2 封版后一次解封留出集）**：50 条 **72.00%（36/50）**，macro-F1 0.7107；dev macro-F1 0.7558（差 −4.51pct），逐类 F1 强弱分布一致（`other` / `diagnosis` 双弱，`advice` / `metric_explain` / `price` 双满分），未见明显过拟合调优集。
- **偏差指纹**：dev 上 `cause` 精确率仅 0.4375（预测 16 次、实际只有 7 条）属过预测；留出集 3 条 `diagnosis` 被判成 `cause`（HO-007 / HO-008 / HO-039），同一偏差跨集合复现。


## 5. V3（27 行，1087 字符）

```text
你是医疗搜索query分类器。将输入的query分为以下11类之一。只输出JSON：{"label": "英文code"}
类别定义：
- method 治疗方案：询问怎么治疗、怎么处理、用什么药、做什么手术等具体做法
- diagnosis 病情诊断：描述自身症状后询问得了什么病、是不是某种病
- disease_express 疾病表述：询问某种疾病的症状、表现、能否治愈
- advice 就医建议：询问去哪里看病、挂什么科、哪家医院或医生好
- attention 注意事项：询问患病、用药或孕期等特殊时期能否做某事、有何禁忌
- price 医疗费用：询问治疗、检查、手术的花费
- result 后果表述：询问某种情况或行为会导致什么后果、危害、影响
- metric_explain 指标解读：询问化验、体检指标数值的含义、是否正常
- cause 病因分析：询问疾病或现象的成因
- effect 功效作用：询问某种药、食物、疗法的作用、效果、副作用
- other 其他：单纯陈述情况、意图不明、或以上类别都不适用时
判定示例：
query: 高血压是什么原因引起的 → {"label": "cause"}
query: 我最近总是头晕，晚上躺下更明显，这是怎么回事 → {"label": "diagnosis"}
query: 痔疮用什么药能治好 → {"label": "method"}
query: 痔疮去医院该挂哪个科 → {"label": "advice"}
query: 孕妇不小心吃了两片去痛片，对胎儿有没有影响 → {"label": "result"}
query: 长期吃板蓝根有什么副作用 → {"label": "effect"}
query: 去年做过阑尾炎手术，现在恢复得挺好的 → {"label": "other"}
query: 有没有宝妈家孩子也这样啊，来说说 → {"label": "other"}
query: 人一天要睡几个小时才正常 → {"label": "other"}
query: 类风湿会遗传给下一代吗 → {"label": "disease_express"}
边界规则：
- diagnosis 与 other 犹豫时：query 提到自身或家人（我/我儿/宝宝/孕妇等）的具体症状、身体变化并求判断，判 diagnosis；只是泛泛询问健康知识、没有任何具体人的症状场景，判 other
- 询问某疾病是否遗传、是否传染、会不会癌变等疾病自身属性，判 disease_express
```

- **改动**：在 V2 的示例末尾追加 2 条（「人一天要睡几个小时才正常」→other、「类风湿会遗传给下一代吗」→disease_express），并新增「边界规则：」段 2 条（diagnosis 与 other 的取舍规则、疾病自身属性归 disease_express 的规则），共 27 行；汇总标题改为「V3 基线评测汇总」，输出 `results_v3.csv`。
- **结果**：总体 **74.00%（111/150）**，比 V2 少 1 条；typical 75.56%（略升）、boundary 71.67%（降 3.33pct）。
- **两条规则一赚一赔**：疾病属性规则纯赚（disease_express 90→100%、metric_explain 80→90%）；而「具体症状判 diagnosis」误伤边界样本——`DB-059 像怀孕吗？` 从 other 被拉成 diagnosis、`DT-010` 的治疗询问被拉成 diagnosis，`other` 反而 29.17→25.00%。
- **V2→V3 翻转**：错变对 4 条（DT-022、DT-050、DT-079、DT-089）、对变错 5 条（DT-010、DT-062、DT-090、DB-044、DB-059），净 −1。典型样本略有收益，代价全部落在边界样本。


## 6. V3.1（24 行，931 字符）

```text
你是医疗搜索query分类器。将输入的query分为以下11类之一。只输出JSON：{"label": "英文code"}
类别定义：
- method 治疗方案：询问怎么治疗、怎么处理、用什么药、做什么手术等具体做法
- diagnosis 病情诊断：描述自身症状后询问得了什么病、是不是某种病
- disease_express 疾病表述：询问某种疾病的症状、表现、能否治愈
- advice 就医建议：询问去哪里看病、挂什么科、哪家医院或医生好
- attention 注意事项：询问患病、用药或孕期等特殊时期能否做某事、有何禁忌
- price 医疗费用：询问治疗、检查、手术的花费
- result 后果表述：询问某种情况或行为会导致什么后果、危害、影响
- metric_explain 指标解读：询问化验、体检指标数值的含义、是否正常
- cause 病因分析：询问疾病或现象的成因
- effect 功效作用：询问某种药、食物、疗法的作用、效果、副作用
- other 其他：单纯陈述情况、意图不明、或以上类别都不适用时
判定示例：
query: 高血压是什么原因引起的 → {"label": "cause"}
query: 我最近总是头晕，晚上躺下更明显，这是怎么回事 → {"label": "diagnosis"}
query: 痔疮用什么药能治好 → {"label": "method"}
query: 痔疮去医院该挂哪个科 → {"label": "advice"}
query: 孕妇不小心吃了两片去痛片，对胎儿有没有影响 → {"label": "result"}
query: 长期吃板蓝根有什么副作用 → {"label": "effect"}
query: 去年做过阑尾炎手术，现在恢复得挺好的 → {"label": "other"}
query: 有没有宝妈家孩子也这样啊，来说说 → {"label": "other"}
query: 类风湿会遗传给下一代吗 → {"label": "disease_express"}
- 询问某疾病是否遗传、是否传染、会不会癌变等疾病自身属性，判 disease_express
```

- **改动**：回退到 V2 正文（删去「边界规则：」小标题与 diagnosis/other 规则，也删去 V3 的「人一天要睡几个小时」示例），只在示例末尾追加 1 条「类风湿会遗传给下一代吗 → disease_express」，并在 Prompt 末行追加一条无标题的规则行「- 询问某疾病是否遗传、是否传染、会不会癌变等疾病自身属性，判 disease_express」，共 24 行；输出 `results_v3_1.csv`。
- **结果**：总体 **70.67%（106/150）**，相对 V3 的 74.00% **−3.33pct**，也低于 V2 4pct；typical 70.00%、boundary 71.67%。
- **关键现象**：规则本身有效（disease_express 90→100%、metric_explain 80→90%），但模型对 `other` 的输出次数从 V2 的 9 次塌到 **2 次**，`other` 准确率 29.17→8.33%（24 条只中 2 条），`result` 75→62.5、`attention` 83.33→75、`method` 81.82→78.79 同时退步。看起来「疾病属性归 disease_express」被泛化成了「凡不确定就往具体类里塞」，挤掉了兜底类。
- **方法论**：V3.1 删掉了看似「有害」的 diagnosis/other 规则反而更差，说明 Prompt 是互相支撑的系统而非可增删的规则清单；干预收益递减（类别定义 +34.7pct ＞ few-shot +4.7pct ＞ 边界规则 ±0）。
- **两条被毙方案（未进入任何版本）**：① 多意图裁决——同一条 query 既问病因又问治法，`DT-003` 金标为 method 而 `DB-011/012` 为 cause，无法自洽；② 副作用切分——`DT-075` 标 result、`DB-036` 标 effect、而类别定义表自称 attention，三处矛盾。二者均因金标口径不一致而放弃，未污染单变量迭代。


## 7. 当前状态与文件清单

eval_batch.py 当前驻留 V3.1（已定版回滚至 V2 + holdout 配置，见 final_archive）

- **迭代期状态**：五版逐轮结果 `results_v0.csv` ~ `results_v3_1.csv` 各 150 行；翻转清单 `flips_v1_v2_gain/loss.csv`、`flips_v2_v3_gain/loss.csv`；汇总标题随版本静态文案变化。
- **定版状态**（`final_archive/final_manifest.json`，16/16 项核验 PASS）：`PROMPT_V0` 回滚为 V2 全文（833 字符 / 22 行）；`DEFAULT_DATA=holdout.csv`、`RESULTS_PATH=results_holdout.csv`；模型与参数不变；密钥唯一来源 `os.environ.get("ZHIPU_API_KEY")`，全仓库扫描无明文密钥；汇总标题改为「基线评测汇总」并注明「本次汇总：holdout 黄金留出集（期末考试）」。
- **验收成绩**：开发集 150 条 74.67% / macro-F1 75.58%；黄金留出集 50 条 72.00% / macro-F1 71.07%，|差| ≤ 5pct 验收线通过；`FORMAT_ERROR` 0。
- **错题与天花板**：留出集 14 条错题中 8 条归因于金标标注噪声、6 条归因于模型能力，按考前预注册清单归因后净准确率 88%；Dev 逐行审计 10–13%、考前预注册 12%、成绩震荡带三重证据互证，合理上限 85–90%。
- **局限**：留出集仅 50 条，二项置信区间约 ±13pct；金标未做双人独立复核。详见 `reports/REPORT.md`。

---

## 入库说明（非迭代期原文）

本文件于 2026-11-06 归档入库时依据本仓库内已核实材料重建：五版 Prompt 全文逐字取自 `prompts/v0.txt` ~ `v3_1.txt`，逐轮数字取自 `results/*.csv`、`reports/f1_macro_report.csv` 与 `final_archive/final_manifest.json`，未引入任何新实验或推测数值。原始《医疗搜索 Query 分类 · Prompt 调优实验归档（V0–V3.1）》全文未随任何可访问的对话记录或本地文件保存，故此处为等价重建而非逐字复制。

入库前已按要求应用三处修改：① 第 2 节标题改为「V0（单行，163 字符）」（实测 163 字符 / 1 行，非「约 90 字符」）；② 文档开头加「本文档为迭代期快照，定版状态以 final_archive/final_manifest.json 为准」；③ 第 7 节状态行补「（已定版回滚至 V2 + holdout 配置，见 final_archive）」。若补发原始文本，将逐字替换并重新提交、重打 v1.0 标签。
