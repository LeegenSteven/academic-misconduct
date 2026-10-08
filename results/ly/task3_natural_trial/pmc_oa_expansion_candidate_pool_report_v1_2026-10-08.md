# PMC natural expansion candidate pool v1

日期：2026 年 10 月 8 日

状态：交付前复核版。共 10 条自然引用候选，来自 6 篇不同施引论文和 10 篇不同被引论文。施引论文日期均在 2018-01-01 至 2026-10-08，已排除当前日期之后的记录。此前重复的被引论文已替换为 PMC9825434 → PMC8111494。每条保留精确 bibliography 引用标记、URL、许可元数据、XML SHA-256 和被引摘要定位；双方标注字段全部留空。

## 质量检查

- 精确 CITED 标记：通过
- XML SHA-256 与本地快照逐条一致：通过
- 许可元数据：齐全；许可类型和重用范围仍由项目负责人按最终发布方式复核
- 原文快照：默认保留在本地，下载和哈希复核方法见 `data/raw/pmc_oa_expansion_source_xml/README.md`
- 日期不晚于 2026-10-08：通过
- 被引 PMCID 唯一：10/10
- 与既有候选/合并试标按 PMCID 的重叠：施引 0 条、被引 0 条
- 完整 Train/Dev/Test、调参和评测集去重：仍需用最终清单复核

## 盲标文件

- pmc_oa_expansion_chen_blind_annotation_v1_2026-10-08.csv：不含李云标签的陈明进盲标表。
- pmc_oa_expansion_ly_independent_annotation_v1_2026-10-08.csv：李云侧空白独立标注表。

候选池不能直接写成最终合格样本数；需先完成双人盲标、证据复核、裁决和一致率计算。
