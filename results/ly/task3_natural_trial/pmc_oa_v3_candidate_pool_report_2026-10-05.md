# PMC natural 候选池 v3（10 条）

状态：候选池已准备，尚未形成最终试标集。10 条均保留完整施引段落、精确引用标记、被引全文摘要、来源 URL、许可和 XML SHA-256；两位标注者字段均留空。

## 数量与来源

- 新候选：10 条
- 施引论文：3 篇（PMC12900525, PMC13583542, PMC13625197）
- 被引论文：10 篇
- 来源：Europe PMC fullTextXML / PMC OA 页面
- 许可：每条的施引和被引 XML 均取得显式许可 URL，具体见 `pmc_oa_v3_source_manifest_2026-10-05.csv`

## 核查边界

候选已与仓库中的 v1/v2 PMC 候选池去重；当前仓库未发现这些 PMCID 已进入现有候选池。正式纳入前仍需用完整的 Train/Dev/Test、调参和评测清单再做一次交叉核对，因此 `overlap_status` 没有写成“已确认无重叠”。

## 下一步

1. 李云填写 `pmc_oa_v3_10_candidates_ly_independent_annotation_v1.csv`。
2. 将不含李云标签的 `pmc_oa_v3_10_candidates_chen_blind_annotation_v1.csv` 发给陈明进独立标注。
3. 收回后保留双方原始表，逐条对照并共同裁决；在此之前不写 `adjudicated_label`，不计入最终合格条数。

## 质量闸门

- 记录数：10
- 施引 XML 哈希齐全：是
- 被引 XML 哈希齐全：是
- 显式许可齐全：是
- 精确引用标记齐全：是
- 最终标签：全部留空（待双方盲标）
