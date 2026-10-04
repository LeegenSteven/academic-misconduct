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
- [交付说明](../../results/ly/task2_demo30/README.md)

30 条都已列出证据、双方字段和当前未完成问题；目前 8 条替换样本完成双标、定位和裁决，22 条仍需陈明进独立复核或补证/合规替换，因此只计 8 条合格。

## 20 条 PMC natural 新引用

- [最终 v3 逐条工作簿](../../results/ly/task3_natural_trial/pmc_oa_v2_final_trial_set_v3_2026-10-04.xlsx)
- [最终裁决报告](../../docs/ly/pmc_oa_v2_final_trial_set_report_v3_2026-10-04.md)
- [原文/BioC 定位核验 CSV](../../results/ly/task3_natural_trial/pmc_oa_v2_source_snapshot_and_locator_verification_v1_2026-10-04.csv)
- [PMC 快照 SHA-256 清单](../../results/ly/task3_natural_trial/pmc_oa_v2_source_snapshot_sha256_manifest_2026-10-04.csv)

20/20 条均已定位、完成双方标注和最终裁决，并确认与现有 train/dev/test、调参和评测集无重叠；最终标签为 ACCURATE 5、NOT_ACCURATE 13、IRRELEVANT 2，原始标签和裁决理由均保留。

## Qwen3 Test 606 条

- [606 条 Test 原始预测（MultiVerS step2141，不是 Qwen3）](../../results/cmj/task4_finetune/test_predictions_step2141.jsonl)
- [Test 原始运行日志](../../results/cmj/task4_finetune/test_eval_step2141.log)
- [训练日志](../../results/cmj/task4_finetune/train_step2141.log)
- [Qwen3/A100 状态核查](../../docs/ly/a100_qwen3_test_audit_ly_2026-10-04.md)

当前没有可复现的 Qwen3 606 条 Test 原始输出、冻结配置和运行日志。仓库中的 606 条预测和日志是 MultiVerS `step2141` 评测材料，已明确标注，不能改称 Qwen3；待模型/检查点、哈希、prompt/模板、解码参数、输入哈希和完整日志补齐后再复算。现有 Test 结果中 IRRELEVANT 类未被正确预测，属于已记录的模型效果问题。

## 其他留痕

`docs/ly/` 已保留数据源许可、去重、证据定位、模型复算就绪性、会议回复和待协作清单；`results/cmj/` 保留训练、Dev/Test、过采样和检索运行结果。新增文件不会覆盖原始回传件或 v2 暂定版本。
