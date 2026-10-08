# PMC 新增 4 条共同裁决回传质量核查 v1

日期：2026 年 10 月 8 日

## 回传完整性

- 原始回传按 GB18030 原字节保存在 pmc_oa_expansion_4_disagreements_joint_adjudication_chen_return_raw_v1_2026-10-08_gb18030.csv。
- 记录数 4；ID 恰为 EXP-01、EXP-03、EXP-05、EXP-07。
- 四个共同字段和共同裁决状态均非空。
- 与发出的裁决表相比，只有 publication_date 从 ISO 格式改为斜杠日期显示；规范化副本恢复为原 ISO 日期，未发现实质底稿字段变化。

## 裁决核查

| 样本 | 回传裁决 | 核查结论 |
|---|---|---|
| EXP-01 | NOT_ACCURATE | 标签理由基本自洽；但 evidence_status 写有“待正文核对”，而 adjudication_status 写“已共同裁决”，且 locator 仅写摘要/讨论，需补全文定位或明确仍待核。不能直接计为最终证据闭合。 |
| EXP-03 | ACCURATE | 按分句/引用标记口径，PMC7333361 只支持“巨大实验努力”分句，数量主张由其他引用承担；该裁决逻辑可接受。 |
| EXP-05 | ACCURATE | 已按被引全文确认 Trimmomatic 的 adapter trimming、quality pruning 和 sliding window 功能，裁决依据充分。 |
| EXP-07 | ACCURATE | 全文可支持武汉 2019 年 12 月早期不明原因肺炎背景，但当前 locator 仍是“摘要; Background/Findings段”，需补精确段落或句子位置。 |

## 当前状态

这次回传可以作为共同裁决记录保存，但暂不能把 4 条全部标成“证据定位已闭合”：EXP-01 需要澄清状态矛盾，EXP-07 需要补精确全文定位。6 条双方标签一致样本仍未填写 joint 字段，因此 10 条新增候选尚未形成 10 条完整共同裁决记录。

规范化回传和 10 条暂存合并表已生成；原始双方标签与师兄原始回传均保留。
