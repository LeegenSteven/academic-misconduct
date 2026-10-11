# 路线二接口试连样例 v1

日期：2026-10-05

这 5 条记录用于成员 3 的路线二接口 smoke test，来自已完成双方标注、证据定位和暂定裁决的 PMC natural 试标集。样例覆盖三类标签：`NOT_ACCURATE`、`ACCURATE`、`IRRELEVANT`。

## ID 口径

- `citation_id`：本组稳定样本 ID，仍可回到 PMC 试标集原表。
- `citing_short` / `cited_short`：OpenAlex 裸 `W` 号（去掉 `https://openalex.org/`）。
- 本文件中的 `cited_doc_id` 暂按成员 3 约定填为 `cited_short`，仅用于接口试连；原始 `source_cited_pmcid` 和 `cited_doi` 同时保留，不能覆盖主数据中的来源标识。
- `edge_id` 留空。该字段由成员 3 的边表生成；本文件提供 `edge_key=citing_short__cited_short` 及 `citation_id` 供回连。

## 核验与限制

- 5 条的施引 DOI 和被引 DOI 均通过 OpenAlex works DOI 查询得到 W 号；查询时被引 W 号均存在于施引作品的 `referenced_works` 中。
- 证据定位沿用 PMC 试标集的定位字段；原始 PMCID、DOI 和标签不改写。
- `score_support`、`score_distort`、`score_unrelated` 统一为 `null`，因为当前尚未完成校准；不能把自报置信度当作概率。
- 这份文件是接口试连副本，不是正式路线二全量数据，也不改变主数据的 `cited_doc_id`。
## 2026-10-10 基线独立复核

成员 3 的 route2_baseline_v1 已按固定提交复核：104 个节点清单与 116 条边表的端点并集均与 57 个 RED 节点零交集。详见 [`route2_baseline_v1_recheck_2026-10-10.md`](route2_baseline_v1_recheck_2026-10-10.md) 和哈希核验表 [`route2_baseline_v1_hash_verification_2026-10-10.csv`](route2_baseline_v1_hash_verification_2026-10-10.csv)。复核同时记录了成员 3 说明文档中脚本 SHA-256 不一致、以及“105 个有边节点”与文件实际 104 个端点节点的口径问题。
## 2026-10-11 复核跟进

成员 3 已将节点数量修正为 104，独立重算与 0 交集结论保持一致。最新提交中脚本实际 SHA-256 仍为 `e781d311...`，而说明文件登记 `db620f0e...`，该单项哈希仍待确认。详见 [`route2_baseline_v1_recheck_followup_2026-10-11.md`](route2_baseline_v1_recheck_followup_2026-10-11.md)。
