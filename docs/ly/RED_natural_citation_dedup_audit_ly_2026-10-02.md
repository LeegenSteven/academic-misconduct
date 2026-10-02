# RED 自然引用排重审计（李云侧）

日期：2026 年 10 月 2 日

## 目的

对 ReferenceErrorDetection seed=42 的 30 条记录，在当前工作区已登记的训练、调参和评测文件中做可复核的重复检索，为后续新来源试标的‘此前未进入本组数据’条件提供依据。该审计只证明检索范围内未发现匹配，不替代双方人工确认。

## 检索范围

- RED 快照：`.repo_upload/data/processed/seed42_source_audit_ly_v19.csv`；SHA-256：`2267D754B53BA51FE1FB6A660445B7DF800C3780943E2CF109731E9E6D245BE8`。
- 已索引目录：`成员2_本周完整交付包/03_数据与代码核验`，共 25 个 JSON/JSONL/CSV/TSV/TXT 文件、24923 条记录。
- 检索键：施引 DOI、被引 DOI、规范化引用语境、规范化被引证据文本；大小写、空白和标点做规范化。
- 未将网页搜索、付费全文、未落盘的运行缓存或未登记的外部数据当作已核验范围。

## 结果

- RED 总记录：30 条；其中当前非排除记录 26 条，排除记录 4 条。
- 施引 DOI 命中：0 条。
- 被引 DOI 命中：0 条。
- 引用语境规范化精确/包含命中：0 条。
- 被引证据文本规范化精确/包含命中：0 条。
- 任一检索键命中：0 条。

在本次登记范围内没有发现 RED 记录与已有训练、调参或评测文件的精确重复命中。这个结果只能作为排重审计证据，不能单独把 RED 记录升级为正式试标集：仍需完成许可边界确认、被引原文证据定位、陈明进盲标、双方裁决和一致率统计。

## 逐条记录

| citation_id | 状态 | 施引 DOI | 被引 DOI | 任一命中 |
|---|---|---|---|---|
| RED:1 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:2 | excluded / 不可用 | 无 | 无 | 无 |
| RED:3 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:4 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:5 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:6 | excluded / 不可用 | 无 | 无 | 无 |
| RED:7 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:8 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:9 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:10 | excluded / 不可用 | 无 | 无 | 无 |
| RED:11 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:12 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:13 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:14 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:15 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:16 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:17 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:18 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:19 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:20 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:21 | excluded / 不可用 | 无 | 无 | 无 |
| RED:22 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:23 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:24 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:25 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:26 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:27 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:28 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:29 | new_pilot / 需补标 | 无 | 无 | 无 |
| RED:30 | new_pilot / 需补标 | 无 | 无 | 无 |

## 使用边界

1. 本审计不修改 `original_label`、`evidence_status`、`project_label` 或任一标注者字段。
2. `natural_or_constructed=natural` 只说明来源记录类型，不等于已满足正式试标的全部纳入条件。
3. 只有双方独立标注并逐条裁决后，才能把通过记录计入新试标集；当前正式合格数量仍记为 0。
