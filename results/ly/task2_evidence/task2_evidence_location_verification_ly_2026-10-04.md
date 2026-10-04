# 60条证据定位个人核验报告

核验日期：2026-10-04
核验人：李云

## 输入版本

- 原始核查表：`陈明进，20261003，606test/task2_evidence_location_check_60_2026-09-22.csv`
- 原始核查表 SHA-256：`625CF86A195A7929EEE8EF47F6EAC7E248F91C45F254FBE678F07ED0E0E1DC5B`
- 证据库：`成员1反馈 Data/multivers-format/corpus.jsonl`
- 证据库 SHA-256：`59F2309E1124C9D2EF8240D9C725E1A9377CED43AE34A13F222C7C42D40D8167`

## 机械定位结果

- 输入行数：60
- `claim_id` 唯一数：60
- `locator_check=是`：60/60
- `locator_check=否`：0/60

逐条按 `model_ev` 中的 `doc_id#sentence_id` 查找 `corpus.jsonl`，并对句子文本做空白归一化后比对。当前 60 条均能回到对应原文句子；这只证明定位可回溯，不等于语义证据已经通过。

## 李云个人语义初审

- `evidence_valid=是`：23 条
- `evidence_valid=否`：17 条
- `evidence_valid=证据不适用`：5 条
- `evidence_valid` 留空待核：15 条

“是”只用于句子直接支持 claim 核心对象和关系的记录；“否”只用于明显无关或缺少 claim 核心对象/关系的记录；部分支持、需要上下文或涉及完整 claim 范围的记录仍留空。该结果是李云个人初审，不是双方独立复核或最终裁决。

## 当前结论

定位部分已完成 60/60；语义初审完成 45/60，仍有 15 条待核。正式 0.80 指标不能用个人初审替代，仍需保留双方原始值并由陈明进独立复核后裁决。

输出文件：`C:\Users\y\Desktop\学术引用不端\成员2_本周任务_2026_09_28\04_证据定位\task2_evidence_location_check_60_李云个人定位核验_v1_2026-10-04.csv`
