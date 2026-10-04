# 2026-10-04 逐条交付索引（李云）

本页按线路一负责人的要求，集中列出可逐条查看的核查、示范修复和 PMC 试标材料。每条记录尽量保留证据位置、双方判断、最终裁决和未完成问题；空值代表该环节尚未完成，不用原始标签代替。

## 两个数据源：seed=42，各 30 条

- [SciFact 30 条逐条 CSV](../../results/ly/task1_seed42_audit/seed42_SciFact_30_row_level_audit_v4_2026-10-04.csv)
- [ReferenceErrorDetection 30 条逐条 CSV](../../results/ly/task1_seed42_audit/seed42_RED_30_row_level_audit_v4_2026-10-04.csv)
- [完整双人核查工作簿](../../data/processed/seed42_adjudicated_pilot_ly_license_corrected_v4_2026-10-03.xlsx)
- [交付说明](../../results/ly/task1_seed42_audit/README.md)

当前合格数按“证据已定位且有最终裁决”统计：SciFact 17/30，ReferenceErrorDetection 26/30，合计 43/60；其余 17 条分别为 SciFact 源文缺失/待核 13 条、RED 不可用/排除 4 条。

## 30 条示范修复

- [30 条逐条状态表](../../results/ly/task2_demo30/demo30_repair_status_30_row_level_2026-10-04.csv)
- [8 条已完成替换的双方裁决明细](../../data/processed/demo30_adjudicated_replacement_pilot_ly_2026-10-03.csv)
- [最终合并与裁决 CSV v3](../../results/ly/task2_demo30/demo30_final_merged_adjudicated_v3_2026-10-04.csv)
- [最终合并与裁决 Excel v3](../../results/ly/task2_demo30/demo30_final_merged_adjudicated_v3_2026-10-04.xlsx)
- [最终合并说明 v3](../../results/ly/task2_demo30/demo30_final_merged_adjudicated_v3_2026-10-04.md)
- [交付说明](../../results/ly/task2_demo30/README.md)

30 条均已列出证据、双方字段、最终工作标签和过程状态。GitHub 最新复核确认版中，30 条示范数据有 28 条可用标签、2 条待定（`demo_17`、`demo_25`）；此前 v3 工作版保留为过程材料，不用旧过程状态覆盖最新确认记录。详见 [`review-confirmed-v1`](../../data/quality_v1/review_confirmation_v1/README.md)。

## 60 条证据定位语义分歧

- [60 条共同裁决 Excel v3](../../results/ly/task2_evidence/task2_evidence_location_check_60_joint_adjudicated_v3_2026-10-04.xlsx)
- [60 条共同裁决报告 v3](../../results/ly/task2_evidence/task2_evidence_location_check_60_joint_adjudicated_report_v3_2026-10-04.md)

60 条均有共同裁决字段；最终 `evidence_valid` 为“是”18 条、“否”37 条、“证据不适用”5 条。原 v2 回传和双方原始值保留不改。

## 正式数据划分与规模估算

- [被引论文分组与规模估算依据](../../docs/ly/pmc_oa_v2_group_split_and_scale_basis_2026-10-04.md)
- [新来源试标与划分方案](../../docs/ly/new_pilot_sampling_and_split_plan_ly_2026-10-03_v2.md)

当前已完成分组规则、泄漏防范原则和估算公式；20 条 PMC 试标仍统一为 `new_pilot`，尚未形成正式 train/dev/test 映射。由于缺少实测纳入率和人工用时流水，正式样本规模、初筛量和工时数值尚未完成，不能写成已完成。

## 20 条 PMC natural 新引用

- [最终 v3 逐条工作簿](../../results/ly/task3_natural_trial/pmc_oa_v2_final_trial_set_v3_2026-10-04.xlsx)
- [最终裁决报告](../../docs/ly/pmc_oa_v2_final_trial_set_report_v3_2026-10-04.md)
- [原文/BioC 定位核验 CSV](../../results/ly/task3_natural_trial/pmc_oa_v2_source_snapshot_and_locator_verification_v1_2026-10-04.csv)
- [PMC 快照 SHA-256 清单](../../results/ly/task3_natural_trial/pmc_oa_v2_source_snapshot_sha256_manifest_2026-10-04.csv)

最新复核确认版中，20 条 PMC 唯一候选有 16 条可用标签、4 条待定；原始重复项 `PMC-OA-V2-08`、`PMC-OA-V2-18` 已由 `PMC-REPAIR-08`、`PMC-REPAIR-18` 替换。直接用于带标签评测时排除待定项，详见 [`review-confirmed-v1`](../../data/quality_v1/review_confirmation_v1/README.md)。

## Sarol quality v1 Dev BM25 核验

- [Dev BM25 top-10 检索结果](../../results/ly/sarol_quality_v1_dev_bm25_v1/)
- [核验状态说明](../../docs/ly/sarol_quality_v1_dev_bm25_status_2026-10-04.md)

修复版 Dev 316 条的 top-10 证据句召回为 0.3484，证据文档召回为 0.6371，claim 级证据句召回为 0.5961，claim 级证据文档召回为 0.7373。该目录是检索覆盖诊断；三分类模型指标待修复版 Train 重训后的匹配预测。

## Qwen3 Test 606 条

- [606 条 Test 原始预测（MultiVerS step2141，不是 Qwen3）](../../results/cmj/task4_finetune/test_predictions_step2141.jsonl)
- [Test 原始运行日志](../../results/cmj/task4_finetune/test_eval_step2141.log)
- [训练日志](../../results/cmj/task4_finetune/train_step2141.log)
- [Qwen3/A100 状态核查](../../docs/ly/a100_qwen3_test_audit_ly_2026-10-04.md)

当前没有可复现的 Qwen3 606 条 Test 原始输出、冻结配置和运行日志。仓库中的 606 条预测和日志是 MultiVerS `step2141` 评测材料，已明确标注，不能改称 Qwen3；待模型/检查点、哈希、prompt/模板、解码参数、输入哈希和完整日志补齐后再复算。现有 Test 结果中 IRRELEVANT 类未被正确预测，属于已记录的模型效果问题。

## 其他留痕

`docs/ly/` 已保留数据源许可、去重、证据定位、模型复算就绪性、会议回复和待协作清单；`results/cmj/` 保留训练、Dev/Test、过采样和检索运行结果。新增文件不会覆盖原始回传件或 v2 暂定版本。
