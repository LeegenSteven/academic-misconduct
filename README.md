# academic-misconduct

学术不端相关研究的代码与数据仓库。

> 本仓库目前为**私有**。`data/raw/` 可能包含涉及具体个人或机构的未脱敏记录，在明确脱敏方案之前请勿转为公开。

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
| demo30 示范修复 | 8/30 | 22 条待协作或补证/替换 | [`30 条状态表`](results/ly/task2_demo30/demo30_repair_status_30_row_level_2026-10-04.csv) |
| PMC natural 新试标集 | 20/20 | 0 | [`最终 v3 工作簿`](results/ly/task3_natural_trial/pmc_oa_v2_final_trial_set_v3_2026-10-04.xlsx) |

这里的“合格”只表示该交付项已具备可回溯证据和最终裁决；不同交付项不能直接相加当作一个最终大数据集。Qwen3 的 606 条 Test 尚未完成：仓库中的 606 条原始预测和日志属于 MultiVerS `step2141`，不是 Qwen3；状态和缺少材料见 [`A100/Qwen3 核查记录`](docs/ly/a100_qwen3_test_audit_ly_2026-10-04.md)。

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
