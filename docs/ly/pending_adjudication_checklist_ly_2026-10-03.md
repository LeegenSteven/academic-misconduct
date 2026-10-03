# 待陈明进确认清单（2026-10-03）

请只对下面列出的分歧/待确认项回复，回复后再写入 `adjudicated_*` 和最终 `project_label`。原始回传表和个人标签均不修改。

## A. demo30（2 项）

| replacement_id | 当前双方值 | 请确认 |
|---|---|---|
| replacement_04 | 陈明进：annotator_1_label=NOT-ACCURATE，candidate_status=不接受替换；李云：annotator_2_label=NOT_ACCURATE | 该候选是否纳入替换集？如不纳入，请确认保留为排除/不接受替换。 |
| replacement_06 | 陈明进：ACCURATE；李云：NOT_ACCURATE。双方定位均为 46% 肝硬化患者发生急性肝功能失代偿，但李云认为 claim 的 12%—50% 数值范围未被证据支持。 | 请给出最终三分类及是否需要补证。 |

## B. SciFact（6 项）

| citation_id | 陈明进 | 李云 | 请确认 |
|---|---|---|---|
| train-78 | NOT_ACCURATE | ACCURATE | 是否按证据句对 caspase-11 与吞噬体-溶酶体融合的条件性作用裁决？ |
| train-788 | NOT_ACCURATE | ACCURATE | 是否按证据句对 Microcin J25 抑制 NTP 结合裁决？ |
| train-309 | NOT_ACCURATE | ACCURATE | 是否按证据句对 DUSP4 过表达增加化疗诱导凋亡裁决？ |
| train-694 | NOT_ACCURATE | ACCURATE | 是否按证据句对 LAV 保护效果与淋巴结 T 细胞反应相关裁决？ |
| dev-528 | NOT_ACCURATE | ACCURATE | 是否按证据句对 HTLV-1 Tax 抗体交叉反应裁决？ |
| train-760 | NOT_ACCURATE | ACCURATE | 是否按证据句对 ACT 对传播降低影响有限裁决？ |

## C. ReferenceErrorDetection（3 项）

| citation_id | 陈明进 | 李云 | 请确认 |
|---|---|---|---|
| RED:23 | NOT_ACCURATE | ACCURATE | 施引句同时列举 COOT、NAMD/MDFF，而被引原文直接支持范围是否足以判 ACCURATE？ |
| RED:28 | NOT_ACCURATE | ACCURATE | 摘要对机器学习原子间势、势能面表示的概括是否足以支持 kernels/descriptors 表述？ |
| RED:30 | NOT_ACCURATE | ACCURATE | 被引原文约 249.5–251 cm−1 的 WSe2 峰及 A1g/E2g 归属是否足以支持施引句的 250 cm−1 A1′/共振峰表述？ |

## D. 记录口径确认（不计入正式一致率）

1. `RED:2`、`RED:6` 被引来源撤稿/不可用，是否确认保持三分类空白、证据状态为待定位，并列入排除记录？
2. `SciFact补证说明_2026-10-02` 中 `SciFact:train-1212` 有两行且 SHA-256 不同。请补充这两行各自对应的文献/文件标识，避免后续合并歧义。

回复时可按“replacement_04：纳入/不纳入；replacement_06：ACCURATE/NOT_ACCURATE/IRRELEVANT；SciFact...；RED...；RED:2/6：排除；train-1212：文件标识...”的格式填写。
