# Task2 60 条语义分歧原文对照报告

核对日期：2026-10-04  
用途：为双方共同裁决保留原始值和同一版 corpus 原文；不覆盖任何独立标注。

## 数据版本

- 陈明进回传：`task2_evidence_location_check_60_陈明进独立复核回传_v3_2026-10-04.csv`
- 李云个人表：`task2_evidence_location_check_60_李云个人定位核验_v1_2026-10-04.csv`
- corpus：`成员1反馈 Data/multivers-format/corpus.jsonl`
- corpus SHA-256：`59F2309E1124C9D2EF8240D9C725E1A9377CED43AE34A13F222C7C42D40D8167`

## 结果

- 原始 `evidence_valid` 不一致共 18 条。
- 其中 12 条是真正的非 IRRELEVANT 语义分歧：`60, 90, 134, 164, 208, 254, 342, 358, 364, 391, 420, 540`。
- 1 条为李云侧待核、师兄填“是”：`141`。
- 5 条为 IRRELEVANT 的字段口径差异：李云使用“证据不适用”，师兄使用二值“是/否”：`166, 314, 390, 477, 548`。

## 使用规则

1. 共同裁决时先看 `model_evidence_from_corpus`，确认句号没有越界。
2. 再看 claim 的对象、关系、方向、范围和数值是否被证据直接覆盖。
3. IRRELEVANT 行先确认 `evidence_valid` 允许的取值，再计算一致率；不能把“证据不适用”事后静默改成“否”。
4. 裁决后保留陈明进值、李云值、双方理由和裁决理由，不能覆盖原始值。

机器生成明细：`task2_evidence_location_check_60_语义分歧原文对照_v1_2026-10-04.csv`。
