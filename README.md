# academic-misconduct

学术不端相关研究的代码与数据仓库。



## 2026-10-04 修复后的训练数据

两位同学本次重训从 [`data/quality_v1/sarol/`](data/quality_v1/sarol/) 取三份 `*-model.jsonl` 和 `corpus.jsonl`。Train2141、Dev316、Test606，标签读显式gold，已修正Train36条及Test3条错配。具体路径调整见 [训练数据使用说明](data/quality_v1/TRAINING_GUIDE.md)。

## 目录结构

```
academic-misconduct/
├── data/           # 数据
│   ├── raw/        # 原始采集数据，只读，永不原地修改
│   ├── interim/    # 清洗中间产物，可随时由 raw 重建
│   └── processed/  # 分析用最终数据，论文结论直接基于此层
├── code/           # 源码
│   ├── cmj/        # 陈明进
│   ├── ly/         # 李云
│   └── shared/     # 两人共用
├── notebooks/      # 探索性分析（cmj/ ly/ 分目录）
├── scripts/        # 数据获取、一键复现脚本
├── results/        # 图表、表格等产出
└── docs/           # 方案、笔记、会议记录
```

## 数据

**原始数据不进版本控制。** 原因有两个：

1. 体积——git 历史只增不减，删掉的大文件仍留在历史里，仓库会越来越难克隆；
2. 敏感性——学术不端记录常涉及真实姓名、机构、举报材料，一旦提交就永久留存且随仓库共享。

`.gitignore` 默认忽略 `data/raw/`、`data/interim/`、`data/processed/` 下的文件，仅放行说明文档和明确登记的脱敏快照。数据的获取与重建方式见 [`data/README.md`](data/README.md) 和 [`scripts/README.md`](scripts/README.md)。

当前李云侧提交包含：`code/ly/` 下的评估与检索脚本、`scripts/fetch_seed42_sources.py` 和 `scripts/validate_seed42_snapshot.py`，以及 `data/processed/seed42_source_audit_ly_v19.csv` 脱敏快照和 `data/processed/seed42_source_audit_ly_v19.xlsx` 完整核查工作簿。两份文件都不包含原始下载包或最终裁决值。

## 2026-10-04 逐条交付状态

线路一负责人要求的逐条查看入口集中在 [`docs/ly/delivery_index_2026-10-04.md`](docs/ly/delivery_index_2026-10-04.md)。当前状态如下：

| 交付项 | 当前合格数 | 未完成/排除 | 逐条入口 |
|---|---:|---:|---|
| seed=42 SciFact 30 条 | 17/30 | 13 条源文缺失/待核 | [`SciFact CSV`](results/ly/task1_seed42_audit/seed42_SciFact_30_row_level_audit_v4_2026-10-04.csv) |
| seed=42 ReferenceErrorDetection 30 条 | 26/30 | 4 条不可用/排除 | [`RED CSV`](results/ly/task1_seed42_audit/seed42_RED_30_row_level_audit_v4_2026-10-04.csv) |
| 两个数据源合计 | 43/60 | 17 条未形成合格样本 | [`完整工作簿`](data/processed/seed42_adjudicated_pilot_ly_license_corrected_v4_2026-10-03.xlsx) |
| demo30 示范修复 | 28/30 | 2 条待定 | [`复核确认版`](data/quality_v1/review_confirmation_v1/README.md) |
| PMC natural 新试标集 | 16/20 | 4 条待定；原始重复项已替换 | [`复核确认版`](data/quality_v1/review_confirmation_v1/README.md) |

这里的“合格”只表示该交付项已具备可回溯证据和可用标签；待定记录不纳入带标签评测。不同交付项不能直接相加当作一个最终大数据集。Qwen3 的 606 条 Test 尚未完成：仓库中的 606 条原始预测和日志属于 MultiVerS `step2141`，不是 Qwen3；状态和缺少材料见 [`A100/Qwen3 核查记录`](docs/ly/a100_qwen3_test_audit_ly_2026-10-04.md)。

修复版 Sarol Dev 的 BM25 top-10 检索覆盖结果见 [`sarol_quality_v1_dev_bm25_v1`](results/ly/sarol_quality_v1_dev_bm25_v1/)。该目录只报告检索召回；修复版 Train 重训后的模型三分类指标待匹配预测文件。

## 2026-10-05 李云侧独立推进

- **Qwen3 Dev 旧输出重评**：已对仓库中已有的 316 条 Qwen3 Dev 原始输出按修复版 Sarol gold 重新计算，Accuracy `0.639241`、Macro-F1 `0.554573`。这一步没有进行新的模型推理，不能替代 A100 上的 Dev 决策和 Test606 新实验；逐条误差、输入、原始输出和重评日志见 [`qwen3_dev_reanalysis_v1`](results/ly/qwen3_dev_reanalysis_v1/)。
- **PMC natural 候选扩充**：新增 10 条候选，来自 3 篇新的施引论文和 10 篇不同被引论文。每条均保留完整施引段落、引用标记、被引全文摘要、许可和 XML SHA-256。李云侧已单独初标 7 条 ACCURATE、3 条 NOT_ACCURATE；陈明进盲标表不含李云标签，10 条在双方标注和共同裁决前不计入最终合格样本。入口见 [`PMC natural v3 candidate report`](results/ly/task3_natural_trial/pmc_oa_v3_candidate_pool_report_2026-10-05.md)。

## 协作约定

| 目录 | 归属 | 规则 |
|------|------|------|
| `code/cmj/` | 陈明进 | 自己的实验代码，随便改，不用等人 review |
| `code/ly/` | 李云 | 同上 |
| `code/shared/` | 共用 | 改动会影响对方，**改之前先说一声** |
| `data/` | 共用 | 只往 `raw/` 追加，不改写已有文件 |
| `results/` | 共用 | 按 `主题/` 分子目录，避免互相覆盖 |

**往 `shared/` 放东西的判定**：同一段逻辑在两边各写了一遍，或者两边都要读同一份数据/同一个常量表——这时候再抽到 `shared/`。别提前设计通用框架。

## 复现

```bash
# 待补充：环境安装、数据获取、跑通全流程的命令
```
