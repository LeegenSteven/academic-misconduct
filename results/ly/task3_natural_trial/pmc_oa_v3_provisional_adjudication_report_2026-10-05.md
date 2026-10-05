# PMC OA v3 10 条：全文核对与临时裁决建议（2026-10-05）

## 状态说明

本文件是基于 PMC 全文快照的**临时裁决建议**，不是双方共同裁决结果。双方原始标注、原始回传文件和对照表均保留；本文件不回写对照表中的 `adjudicated_label`。

- 样本数：10
- 标签一致：5 条
- 标签分歧：5 条（V3-02、V3-03、V3-04、V3-07、V3-08）
- 陈明进原始回传文件 SHA-256：`0BDCD570F7DB28D79B427F02E6E4E733E3B4F789AF6181F662FE987BCB346887`
- 原始回传编码：GB18030；文件按原字节保留

## 临时建议

| 样本 | 双方标签 | 临时建议 | 状态 | 全文核对要点 |
|---|---|---|---|---|
| PMC-OA-V3-01 | ACCURATE / ACCURATE | ACCURATE | 一致，待共同确认 | 双方标签一致；目标文献与施引语境均支持根管封闭材料应具有生物相容性和非毒性。 |
| PMC-OA-V3-02 | NOT_ACCURATE / ACCURATE | — | 待共同裁决 | 全文支持施引段中关于根尖周组织耐受/生物相容性的部分，但该施引段还包含易于置入、工作时间和理化性质等多个并列断言。 |
| PMC-OA-V3-03 | NOT_ACCURATE / ACCURATE | NOT_ACCURATE | 来源核对后建议修订 | 全文明确将根管封闭剂的 adhesion 定义为对牙本质和牙胶尖的黏附，并指出相关 attachment 涉及机械嵌合力，而不是施引句所称的 molecular attraction。 |
| PMC-OA-V3-04 | NOT_ACCURATE / ACCURATE | NOT_ACCURATE | 来源核对后建议修订 | 全文支持 AH-Plus、干燥根管、CHX 以及断裂模式的若干事实，但目标文献使用的是 Endosequence BC；施引段写成 Sealer Plus BC，且整段包含多项并列结论。 |
| PMC-OA-V3-05 | NOT_ACCURATE / NOT_ACCURATE | NOT_ACCURATE | 一致，待共同确认 | 双方标签一致，且证据状态一致；保留原始标签与理由，不改写双方原值。 |
| PMC-OA-V3-06 | NOT_ACCURATE / NOT_ACCURATE | NOT_ACCURATE | 一致，待共同确认 | 双方标签一致，且证据状态一致；保留原始标签与理由，不改写双方原值。 |
| PMC-OA-V3-07 | ACCURATE / NOT_ACCURATE | — | 待共同裁决 | 全文支持手性差异及其对生物/肿瘤过程的影响，也支持 MS/蛋白质组学用于研究相关修饰；但施引句把“simple and rapid exploration”与生物学表现写在同一多引文句中，单个目标引用未必覆盖全部断言。 |
| PMC-OA-V3-08 | NOT_ACCURATE / ACCURATE | ACCURATE | 来源核对后建议保留 | 全文直接讨论成年期 PNN 的降解/重塑、神经可塑性以及关联、空间、社会和听觉学习/记忆效应；目标文献覆盖施引段的核心事实。 |
| PMC-OA-V3-09 | ACCURATE / ACCURATE | ACCURATE | 一致，待共同确认 | 双方标签一致，且证据状态一致；保留原始标签与理由，不改写双方原值。 |
| PMC-OA-V3-10 | ACCURATE / ACCURATE | ACCURATE | 标签一致，但理由需修正 | 标签双方均为 ACCURATE；全文 p=3 支持脑老化伴随胶质细胞反应、神经炎症和神经元退化等施引内容。 |

## 需要共同确认的规则问题

1. **V3-02**：目标文献支持施引段中的根尖周组织耐受/生物相容性部分，但施引段还包含多个并列断言。需要确认按完整施引段整体支持，还是按引用覆盖的分句判断。
2. **V3-04**：全文出现 `Endosequence BC`，施引段写成 `Sealer Plus BC`。需要确认是否为可追溯的同一材料/别名；若不能证明，不能把产品名不一致的整段直接判为 ACCURATE。
3. **V3-07**：这是多引文句。目标文献支持生物手性效应和相关 MS/蛋白质组学研究，但“simple and rapid exploration”可能属于另一引用。需要先确认多引用分句归属口径。

## 建议的下一步

- 保留本文件作为来源核对和讨论底稿；不要把 `recommended_label_provisional` 直接写入 `adjudicated_label`。
- 请陈明进确认 V3-02、V3-03、V3-04、V3-07、V3-08 的共同裁决，并修正 V3-10 与 V3-09 重复的理由。
- 双方确认后，再生成带裁决理由的正式 v2 文件，并重新计算这 10 条的最终一致/裁决统计。

## 关联文件

- `pmc_oa_v3_10_candidates_chen_blind_annotation_return_raw_2026-10-05_gb18030.csv`：陈明进原始回传（原字节保留）
- `pmc_oa_v3_10_candidates_bilateral_comparison_v1_2026-10-05.csv`：双方逐条对照；`adjudicated_label` 当前留空
- `pmc_oa_v3_bilateral_source_check_notes_2026-10-05.md`：来源和字段核对说明
