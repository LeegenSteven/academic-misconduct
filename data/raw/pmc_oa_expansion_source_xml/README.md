# PMC expansion source snapshots

本目录对应 `data/interim/pmc_oa_expansion_candidate_pool_v1_2026-10-08.json` 中的
`citing_xml_sha256`、`cited_xml_sha256` 和 `local_snapshot` 字段。

原始 PMC fullTextXML 快照保留在本地工作目录，默认不随仓库提交；这是为了避免把来源站点的原始文件和许可范围误当成项目自有数据公开发布。需要复核时，可按 JSON 中的 `citing_url`、`cited_url` 下载同一 PMCID 的 XML，并计算 SHA-256 与清单比对。

复核要点：

- 确认施引 XML 中 `reference_id` 对应的 `<ref>` 包含清单中的被引 PMCID；
- 确认 `citing_context_marked` 中的 `<CITED:PMCID|...>` 与该引用编号一致；
- 确认 `cited_evidence` 与被引 XML 的摘要文本一致；
- 按 JSON 中的 SHA-256 核对下载文件。网络接口返回内容变化时，应保留下载时间、URL、HTTP 状态和新哈希，不要覆盖旧记录。

本批候选仍需完成双方盲标、证据复核、裁决及最终 Train/Dev/Test、调参和评测集去重后，才能计算合格样本数；本批记录不等同于最终数据集。
