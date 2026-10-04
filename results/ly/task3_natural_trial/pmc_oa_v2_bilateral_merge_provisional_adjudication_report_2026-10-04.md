# PMC natural 候选双标合并与暂定裁决报告

核验日期：2026-10-04
核验人：李云

## 文件版本

- 陈明进原始修订版：`pmc_oa_v2_陈明进独立标注_2026-10-03_原始修订版.xlsx`
- 陈明进原始修订版 SHA-256：`C17E46D5B225FF7E596494996A2AA112BA5863526AA8B1A6E01B87ACE25FB8F8`
- 李云独立复核版：`pmc_oa_candidate_pool_ly_v2_李云独立标注_v1_2026-10-04.xlsx`
- 李云独立复核版 SHA-256：`3ED2078F1B3794028475603B0676B4CB50B9BAF03A9C5E40C3813CEB3B1221CA`
- 双方合并与暂定裁决版：`pmc_oa_v2_双方标注合并与暂定裁决_v1_2026-10-04.xlsx`
- 双方合并版 SHA-256：`A9910F98C2209601D8C59558203E1010A1441F952F837381FE577AB76388DEC8`

## 双标结果

共 20 条，全部为 `natural`。陈明进原始标签中有 1 条写为 `NOT-ACCURATE`；比较前仅将这一写法规范化为 `NOT_ACCURATE`，原始单元格保留不改。

- 陈明进原始标签：`ACCURATE` 7、`NOT_ACCURATE` 10、`NOT-ACCURATE` 1、`IRRELEVANT` 2
- 规范化后陈明进标签：`ACCURATE` 7、`NOT_ACCURATE` 11、`IRRELEVANT` 2
- 李云独立标签：`ACCURATE` 5、`NOT_ACCURATE` 13、`IRRELEVANT` 2
- 原始字符串完全一致率：17/20 = 0.85
- 规范化标签一致率：18/20 = 0.90
- 分歧：`PMC-OA-V2-05`、`PMC-OA-V2-12`

## 暂定裁决

两条分歧均暂裁为 `NOT_ACCURATE`：

- `PMC-OA-V2-05`：被引摘要说明化生性乳腺癌具有化疗耐药性，但没有直接比较其标准化疗反应与传统 TNBC。
- `PMC-OA-V2-12`：被引摘要只显示一项研究把脂肪含量列为牛奶属性之一，不能支持“已被多位研究者广泛研究”。

暂定裁决标签统计：`ACCURATE` 5、`NOT_ACCURATE` 13、`IRRELEVANT` 2。合并表保留双方原值，`project_label` 暂留空，`adjudicated_label` 仅表示证据定位完成前的暂定语义裁决。

## 来源分层

按施引论文分层的规范化标签一致率：

- 基底动脉夹层治疗来源：4/4 = 1.00
- 化生性乳腺癌来源：3/4 = 0.75
- 斯里兰卡牛奶属性来源：4/5 = 0.80
- 咖啡因运动恢复来源：6/6 = 1.00
- IVF 0PN 胚胎来源：1/1 = 1.00

歪曲类额外报告采用“双方均标 `NOT_ACCURATE` / 任一方标 `NOT_ACCURATE`”的重合率：11/13 = 0.846。该定义已在此处写明，避免与其他项目口径混用。

## 未完成项

20 条的 `annotator_1_evidence_status` 和 `annotator_2_evidence_status` 均保留为“待定位”。因此本文件已完成双标、分歧记录和暂定裁决，但仍不是最终正式试标集；完成源文稳定定位、排除重复或不合格样本后，才能填写正式 `project_label` 并作为正式试标集统计。
