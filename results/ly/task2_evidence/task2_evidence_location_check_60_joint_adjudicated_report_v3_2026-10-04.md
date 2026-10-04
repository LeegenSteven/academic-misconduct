# 60 条证据定位共同裁决报告（v3）

日期：2026-10-04

## 处理对象

- 原始共同复核对照表：	ask2_evidence_location_check_60_双方复核对照_陈明进裁决_v2_2026-10-04.xlsx
- 语义分歧裁决表：	ask2_evidence_location_check_60_语义分歧_陈明进裁决_v2_2026-10-04.xlsx
- 本报告对应的最终工作表：	ask2_evidence_location_check_60_双方共同裁决_v3_2026-10-04.xlsx

## 裁决结果

- 总记录：60 条
- 唯一 claim_id：60 个
- 新增共同裁决字段空值：0
- 最终 joint_adjudicated_evidence_valid：是 18 条、否 37 条、证据不适用 5 条
- claim_id=141：按同版 gold evidence 复核后，最终为“是”
- claim_id=166、314、390、477、548：原记录为 IRRELEVANT 且无 gold evidence，统一记为“证据不适用”，没有改写项目标签

## 处理规则

1. 原 v2 表中的双方原始复核字段全部保留，没有覆盖。
2. 在末尾新增 joint_adjudicated_evidence_valid、joint_adjudication_reason、joint_adjudicator_id 三列。
3. 语义分歧沿用陈明进 v2 裁决值和理由；claim_id=141 补做共同裁决。
4. IRRELEVANT 行的证据有效性按“不适用”记录，避免把无证据样本误判为“是/否”。

## 校验

- 输出文件 SHA-256：$outHash
- 已检查记录数、唯一 ID、共同裁决新增字段空值和 5 条 IRRELEVANT 行，均符合预期。

本文件完成的是“60 条证据定位中的语义分歧共同裁决”这一项；不等同于 Qwen3 606 条 Test 复算或 Dev 0.80 指标完成。
