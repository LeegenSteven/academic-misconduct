# PMC 新增 6 条一致样本来源与证据核查 v1

日期：2026 年 10 月 8 日

范围：PMC-OA-EXP-02、04、06、08、09、10。本审计不修改双方原始标签、理由或共同裁决字段。

## 结果

- 双方标签一致：6/6。
- 施引文献精确 xref 可回溯：6/6。
- 本地 XML SHA-256 与候选池登记值一致：施引 6/6，被引 6/6。
- 许可元数据齐全：6/6；其中 EXP-08、EXP-09 需要对外再分发前单独确认许可范围。
- 排除本批 expansion 文件和原始 XML 后，仓库现有文件中未发现这 6 个 PMCID 的其他 Train/Dev/Test、调参或评测记录；完整外部清单仍需负责人最终确认。

## 需要修正或补充的地方

- EXP-04 的 CR5 在施引 XML 中出现于多个段落。应把定位细化为包含“structures of around 100,000 unique proteins”的首个段落，而不能只写“paragraph containing xref”。
- EXP-08 的现有摘要定位能支持 betacoronavirus，但不能单独覆盖“RNA”和“enveloped”两个限定词。应补充被引全文中 RNA genome 和 envelope spike 的 section/paragraph 定位。
- EXP-10 的标签有全文依据，但应在 joint_evidence_locator 中明确 co-fractionation 讨论所在正文段落。
- EXP-02、06、09 的标签和定位证据可用；双方 evidence_status 的“摘要已支持”和“已定位”属于字段口径差异，不能当作标签分歧。

## 结论

这 6 条可以暂记为“双方标签一致、来源可回溯”，但其中 EXP-04、EXP-08、EXP-10 的定位字段仍需补强；EXP-08、EXP-09 的许可也不能直接等同于可任意再分发全文。它们在共同裁决字段完成前，不写入最终合格样本统计。

机器可读明细见同目录下的 pmc_oa_expansion_6_agreement_source_audit_v1_2026-10-08.csv。
