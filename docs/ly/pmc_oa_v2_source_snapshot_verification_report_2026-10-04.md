# PMC natural 候选原文快照与证据定位核验报告

核验日期：2026-10-04；核验人：李云

- 候选池：`data/interim/pmc_oa_candidate_pool_ly_v2_2026-10-03.json`
- 候选池 SHA-256：`4759890DB0C2882A3C9F43C98CD880456EBEE0703F7FF4DF24CC6A37110A7B27`
- 记录数：20 条；唯一施引 PMCID：5 个；唯一被引 PMCID：16 个。
- 下载接口：`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={PMCID}&retmode=xml`
- 下载日期：2026-10-04

## 机器核验结果

- 施引和被引 XML 快照共 21 个；登记的 `citing_xml_sha256` / `cited_xml_sha256` 与本次下载文件 **21/21 完全匹配**。
- 20/20 条候选的施引语境可回溯到施引论文 XML 段落。
- 20/20 条候选的 `cited_evidence` 可回溯到被引论文 ABSTRACT 的 XML 段落。
- 20/20 条候选也能在同一版本的 NCBI BioC JSON 中回溯到 passage 和 offset。
- `PMC-OA-V2-05` 和 `PMC-OA-V2-16` 的 evidence 字段跨两个摘要 passage，已保留多段定位。

明细文件：`results/ly/task3_natural_trial/pmc_oa_v2_source_snapshot_and_locator_verification_v1_2026-10-04.csv`

## 口径与限制

每条同时记录施引 PMCID/XML 段落、被引 PMCID/摘要段落、BioC `passage_index`、字符 `offset` 和 XML SHA-256。当前以 XML 段落和 BioC passage 为稳定定位，未声称 PDF 页码。

这份报告不覆盖双方原始标签，不把候选池自动改写成最终数据集。正式 `project_label`、完整数据集去重确认和最终版本冻结仍需按项目字段口径完成。
