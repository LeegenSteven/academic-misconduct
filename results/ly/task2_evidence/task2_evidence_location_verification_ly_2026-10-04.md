# 60条证据定位个人核验报告

核验日期：2026-10-04
核验人：李云

## 输入版本

- 原始核查表：`C:\Users\y\Desktop\学术引用不端\陈明进，20261003，606test\task2_evidence_location_check_60_2026-09-22.csv`
- 原始核查表 SHA-256：`625CF86A195A7929EEE8EF47F6EAC7E248F91C45F254FBE678F07ED0E0E1DC5B`
- 证据库：`C:\Users\y\Desktop\学术引用不端\成员1反馈 Data\multivers-format\corpus.jsonl`
- 证据库 SHA-256：`59F2309E1124C9D2EF8240D9C725E1A9377CED43AE34A13F222C7C42D40D8167`

## 机械定位结果

- 输入行数：60
- `claim_id` 唯一数：60
- `locator_check=是`：60/60
- `locator_check=否`：0/60

逐条按 `model_ev` 中的 `doc_id#sentence_id` 查找 `corpus.jsonl`，并对句子文本做空白归一化后比对。当前 60 条均能回到对应原文句子；这只证明定位可回溯，不等于语义证据已经通过。

## 语义证据状态

- `evidence_valid=是`：7 条（模型句与至少一条金标准证据句完全一致）
- `evidence_valid=证据不适用`：5 条（金标准证据为空，通常为 IRRELEVANT 记录）
- `evidence_valid` 留空待核：48 条（定位已回溯，但需要人工判断是否支持完整 claim）

待核项没有被写成“是”，也没有用机械的“不等于金标准句”直接判成“否”。因此这份表是李云侧定位核验版，不是最终 60 条语义证据验收结果；正式 0.80 指标仍不能据此宣称达标。

## 输出

- `C:\Users\y\Desktop\学术引用不端\成员2_本周任务_2026_09_28\04_证据定位\task2_evidence_location_check_60_李云个人定位核验_v1_2026-10-04.csv`

下一步应逐条审阅待核项的 claim 与 model evidence，填写 `evidence_valid` 和理由；若需要正式双人验收，仍需陈明进对同一批 60 条独立填写并保留双方原值。
