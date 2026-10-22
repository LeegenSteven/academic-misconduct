# Sarol 45 条错引漏检全量索引

生成日期：2026-10-20。筛选范围为冻结的 Sarol Test606：gold=NOT_ACCURATE、M0=NOT_ACCURATE、Mbio=ACCURATE。恰好 45 条，未按人工复核结果筛除样本。

## 文件与使用

- `miss45_review.csv`：本周 45 条复核主表。Excel 打开后按列筛选，双方各填自己的标签、证据编号、理由、原因码、日期及预测暴露情况。
- `miss45_payload.jsonl`：45 条完整原始输入、候选证据、M0/Mbio 原始响应及完整记录、冻结 gold 和金证据引用。主表的 payload_line 从 1 起，与此文件逐行对应。
- `paired_transitions.csv`：固定 606 条逐条配对，包含 gold、两模型预测、修复/退化标记及 45 条筛选标记；1 条 M0 INVALID 仍在原分母内。
- `paired_summary.json`：所有核心统计及完整 45 个 ID，含 9 条修复与额外 2 条漏判的 ID。
- `prior_review/review20_final.jsonl`：此前已确认的 20 例只读存档；`review20_overlap.jsonl` 是其中与本 45 条重合的 sarol:test:51，复用其原判断和理由。
- `gold_questions_sidecar.jsonl`：初始空表，后续疑似金标问题另行记录；当前为空不表示 gold 已经全部人工核验无误。
- `source_manifest.json`、`index_audit.json`：源文件路径、哈希、实际源仓库 commit 与核对结果。

同一条只维护主表一行，不为重合案例再建第二份人工表。此前 20 例只有 test:51 与本清单重合；其余 44 条尚待两人逐条复核。该重合条目的本周原因码与暴露记录也仍需补齐，当前 45 条原因码均未自动代填。

## 统计口径

| 统计 | 数量与含义 |
|---|---|
| 修复 / 新增错误 / 净增正确 | 186 / 51 / 135 |
| 修复按 gold 分类 | ACCURATE 177、NOT_ACCURATE 9 |
| 新增错误按 gold 分类 | NOT_ACCURATE 45、IRRELEVANT 6 |
| NOT_ACCURATE 召回 | M0 132/170，Mbio 96/170，少 36 条 |
| 36 的分解 | 45 条新增漏检减 9 条修复 |
| NOT_ACCURATE 被判 ACCURATE | 24/170 增为 71/170，净增 47 |
| 47 的分解 | 原来判对的 45 条，加原来判 IRRELEVANT 的 2 条 |
| SciCiteVal Mscv 对照 | 修复 19、新增错误 9；NOT_ACCURATE 召回 52/89 增为 67/89 |

45、36、47 衡量不同集合，不能混作同一个数。

## 复核填写规则

两模型预测在本表与 payload 中可见，当前按非盲复核管理。每位复核者填写实际是否看过预测。旧 test:51 的历史暴露状态未单独记录，保留 unknown_from_prior_record；不能据文件名推定未暴露。

原因码可多选，用分号分隔：SEM 语义误读、RET 检索遗漏、CTX 输入证据不足、ATT 引用归属、FMT 格式解析、PIPE 实际工程错位或截断、UNK 待核。SEM 子码为否定、方向、数量、条件、对象、过度概括。RET 须指向原检索语料内的证据，PIPE 须附日志。未复核时留空；UNK 也须由实际复核者填写具体待核原因，不能自动填满。

payload 的 gold_reference_spans_diagnostic_only 取自原 gold 引用的源语料句子，句号索引从 0 起。每句标明是否进入原模型候选；标为 false 的额外句子只能用于检索诊断，不能冒称模型已经看到。45 条中 10 条原 gold 的 evidence_missing=true，仍保留其明确分类标签和原记录，不凭缺金证据删除样本。

gold_question_status 初始为 not_reviewed_for_this_week。疑点另写 sidecar，注明原 gold、疑点、双方意见及证据路径，正式 gold 和指标保持原值。本阶段仅生成全量索引，未运行模型、未完成新的 44 条双人判断或 45 条归因。

## 复算

在仓库根目录执行以下命令，并把 review20 路径替换为实际归档文件。使用新输出目录，避免覆盖人工填写内容。Node 依赖使用已配置的 @oai/artifact-tool；生成 CSV 的脚本为 `code/ly/write_route1_miss45_tables_v3.mjs`。

```text
python code/ly/build_route1_miss45_index_v3.py --phase prepare --review20 <20例最终记录.jsonl> --output-dir <新输出目录> --tables-json <中间表.json>
node code/ly/write_route1_miss45_tables_v3.mjs <中间表.json> <QA目录>
python code/ly/build_route1_miss45_index_v3.py --phase finalize --output-dir <新输出目录>
```

源 v2 数据、模型响应与既有 20 例判断均按文件哈希和 (dataset, split, claim_id) 连接；606 条未丢失、45 条无重复，完整原始输出保留在 payload。生成器本身的文件哈希单列，不将未提交脚本伪称已属于源仓库 commit。
