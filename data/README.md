# 数据

三层目录，**只能从上游流向下游**：

```
raw/  ──清洗脚本──▶  interim/  ──分析脚本──▶  processed/
只读                  可重建                论文结论基于此
```

| 目录 | 放什么 | 能不能改 |
|------|--------|----------|
| `raw/` | 采集/下载得到的原始数据 | **不能改**。发现错误就重新采集一份新文件，保留旧的 |
| `interim/` | 清洗、去重、字段对齐的中间产物 | 随便改，随时删掉重跑 |
| `processed/` | 分析脚本直接读取的最终表 | 由脚本生成，不要手工编辑 |

## 数据不进 git

这三个目录下的**文件**都被 `.gitignore` 忽略，只有 `README.md` 会进版本控制。

每个数据集需要登记下面两样东西，缺一不可：

1. `scripts/` 里的获取脚本（能一键重建这份数据）
2. 本文件下方的数据字典条目

## 数据字典

#### seed=42 source audit snapshot (ly v19)

- **来源**：SciFact `release/latest` 与 ReferenceErrorDetection `main` 数据集；来源入口和许可信息随行记录。
- **获取**：`python scripts/fetch_seed42_sources.py`（只写入本地 `data/raw/`，原始数据不进 Git）。
- **快照**：`data/processed/seed42_source_audit_ly_v19.csv`
- **版本/hash**：CSV SHA-256 `2267D754B53BA51FE1FB6A660445B7DF800C3780943E2CF109731E9E6D245BE8`；对应工作簿为本地 v19，工作簿 hash 见项目留痕，不提交二进制工作簿。
- **规模**：60 行 × 24 列；SciFact 30 条、ReferenceErrorDetection 30 条。
- **粒度**：一行代表一条来源核查记录（引用上下文—被引文献配对）。
- **字段**：保留来源入口、许可、版本/hash、引用文本、原始标签/证据状态、李云侧 `annotator_2_*` 状态/初判/定位/理由、划分和排除状态；`project_label` 与 `adjudicated_*` 保持为空。
- **已知问题**：SciFact 为 `constructed` claim；RED 的 RED:2、RED:6 仍为待定位/排除。此快照是李云侧阶段结果，不是双人裁决后的正式数据集。
- **敏感性**：不含原始下载包或本机路径；保留论文引用文本和 DOI，仅限私有仓库内部研究使用，不应直接公开发布。

#### Sarol 三分类 v2（cmj，interim）

- **来源**：Sarol 2024 路线一原始数据（`Citation-Integrity`），经 `code/cmj/convert_three_class_v2.py` 转换。
- **获取**：原始数据经 `scripts/download_papers.py` 拉取后，运行 `python code/cmj/convert_three_class_v2.py` 重建。
- **快照**：`data/interim/converted-three-class-v2/claims-{train,dev,test}.jsonl`
- **版本/hash**（SHA-256）：
  - claims-train：2141 行，`43c2f9dc474e2d10c91da7b752407d04d31c77d5034a3920ad9db16c01058026`
  - claims-dev：316 行，`6281a95a26b1111261d60599da67314d05b122b27b1e9dbb7d32623efb782414`
  - claims-test：606 行，`b458c9ea7acb8630144652e732a846afdfac29230c20a61e402c628929890b50`
- **粒度**：一行一条 claim；`evidence` 为 `{doc_id:[{"sentences":[n],"label":"..."}]}`，无证据为 `{}`。
- **标签**：ACCURATE / NOT_ACCURATE / IRRELEVANT；id 为字符串；Dev 缺 id=199，Train 缺 id=2115。
- **已知问题**：部分样本 evidence 为空（源文缺失）；NEI 仅作无候选时模型输入占位，不替代金标准 IRRELEVANT。
- **敏感性**：含原始 claim 文本，仅限私有仓库内部使用。

#### Sarol 文献语料 corpus（cmj，raw）

- **来源**：Sarol 2024 路线一文献语料，`Citation-Integrity` multivers-format。
- **获取**：`python scripts/download_papers.py`。
- **快照**：`data/raw/multivers-format/corpus.jsonl`
- **版本/hash**：8515 行，SHA-256 `59f2309e1124c9d2ef8240d9c725e1a9377ced43ae34a13f222c7c42d40d8167`。
- **粒度**：一行一篇被引文献；字段 doc_id（int）/ title（多为空）/ abstract（句子数组，按 sentence 编号取句）。
- **已知问题**：标题字段大量缺失；仅含与 claim 相关的摘要集合，部分 claim 的真正被引文献未收录（源文缺失）。
- **敏感性**：公开文献摘要，可内部使用。

> 每接入一份数据集，在下面追加一段。字段含义写清楚，否则三个月后没人（包括你自己）知道 `flag3` 是什么。

### 模板

```markdown
#### <数据集名称>

- **来源**：URL / 数据库名 / 提供方
- **获取**：`python scripts/fetch_xxx.py`
- **版本**：抓取日期或数据快照日期（YYYY-MM-DD）
- **规模**：行数 × 列数，文件大小
- **粒度**：一行代表什么（一篇论文？一次撤稿事件？一个作者？）
- **字段**：
  | 字段 | 类型 | 含义 | 缺失情况 |
  |------|------|------|----------|
  | `id` | str | 唯一标识 | 无 |
- **已知问题**：编码、时区、重名、重复行等
- **敏感性**：是否含真实人名/机构名；能否公开
```

## 伦理与合规

- 涉及**具体个人**的记录（被撤稿作者、举报人、涉事学生）在 `raw/` 里怎么存都行，但**不要**复制到 `results/`、`docs/`、notebook 输出或任何准备公开的材料里。
- `processed/` 默认视为**不可公开**，除非该数据集明确做过脱敏并在此处标注。
- 需要对外发布数据时，另建一个脱敏后的导出目录，并记录脱敏规则。
