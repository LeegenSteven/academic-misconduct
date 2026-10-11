# route2_baseline_v1 独立复核记录（2026-10-10）

## 复核范围

本次复核使用成员 3 提供的 `citation-integrity-lab/citation-integrity-lab` 固定提交：

- 提交：`f1d82b3117fbc5b2b021d49ab8b358e67d7f0b17`
- 来源：[https://github.com/citation-integrity-lab/citation-integrity-lab/tree/f1d82b3117fbc5b2b021d49ab8b358e67d7f0b17](https://github.com/citation-integrity-lab/citation-integrity-lab/tree/f1d82b3117fbc5b2b021d49ab8b358e67d7f0b17)
- 说明文件：`docs/route2/member3/route2_baseline_v1说明.md`
- 复核目标：确认 116 条边、104 个路线二节点与 RED 30 条映射得到的 57 个唯一节点之间的交集。

## 哈希核验

逐个对 Git 提交中的 blob 计算 SHA-256，并与说明文件第四节登记值比较。原始结果见 [`route2_baseline_v1_hash_verification_2026-10-10.csv`](route2_baseline_v1_hash_verification_2026-10-10.csv)。

| 文件 | Git blob SHA-256 | 说明文件登记值 | 结果 |
|---|---|---|---|
| `data/route2/member3/final_edges_no_selfcite.csv` | `85fd4d6c4b35f7febea95a26fa906421cdacc0009227cdf443725f07f394f0e2` | `85fd4d6c4b35f7febea95a26fa906421cdacc0009227cdf443725f07f394f0e2` | 一致 |
| `data/route2/member3/final_top_candidates_v2.csv` | `44d4e64180dd09f610a84001f6c5d3077464c4ba13a0d89ca65cb6ac9f8ea25d` | `44d4e64180dd09f610a84001f6c5d3077464c4ba13a0d89ca65cb6ac9f8ea25d` | 一致 |
| `scripts/route2/member3/run_cidre_on_openalex.py` | `e781d3119632992a42511e394998830a09b7ccc40441e2fdeb84a31c740108fd` | `42a3d01a589f6742a0f7444e9827b5afc7152f1dbd2158641a158d9a3ca206d1` | 不一致 |
| `data/route2/member3/route2_baseline_v1_nodes_104.csv` | `fbef74100fd926b314ab917079ac05932109d9bffcea521478494bcee11cc406` | `fbef74100fd926b314ab917079ac05932109d9bffcea521478494bcee11cc406` | 一致 |
| `data/route2/member3/red_doi_to_w_mapping.csv` | `7305ea2f6775ca3a899dd9913d3fa5e91fc947e8120cff8bcb62b037447eb637` | `7305ea2f6775ca3a899dd9913d3fa5e91fc947e8120cff8bcb62b037447eb637` | 一致 |

其中，边表、Top 候选、节点清单和 DOI→W 映射的 Git blob 与登记值一致。`run_cidre_on_openalex.py` 的 Git blob 为 `e781d3119632992a42511e394998830a09b7ccc40441e2fdeb84a31c740108fd`，与说明文件登记的 `42a3d01a589f6742a0f7444e9827b5afc7152f1dbd2158641a158d9a3ca206d1` 不一致；该脚本不参与本次节点交集计算，需成员 3 后续确认登记值或脚本版本是否写错。这个差异不能标作“全部哈希通过”。

## 独立重算方法

- 路线二节点清单：读取 `route2_baseline_v1_nodes_104.csv` 的 `node_id` 列。
- 路线二边表节点：读取 `final_edges_no_selfcite.csv` 的 `citing_short` 与 `cited_short` 两列并集。
- RED 节点：读取 `red_doi_to_w_mapping.csv` 的 `citing_w` 与 `cited_w` 两列并集。
- 所有比较均使用去掉空白后的裸 `W` 号；不把 `POSITIVE_TEST` 或其他接口结果行混入 RED 映射。

## 重算结果

| 项目 | 结果 |
|---|---:|
| 节点清单行数 | 104 |
| 节点清单唯一节点数 | 104 |
| 边表行数 | 116 |
| 边表唯一 `edge_id` 数 | 116 |
| 边表自引边数（`citing_short == cited_short`） | 0 |
| 边表端点并集节点数 | 104 |
| RED 映射行数 | 30（`RED:1`–`RED:30` 各 1 行） |
| RED 唯一节点数 | 57 |
| 节点清单 ∩ RED 节点 | **0** |
| 边表端点并集 ∩ RED 节点 | **0** |

两个交集均为空，没有可列出的共同 `W` 号。因此成员 3 报告的“104 个路线二节点 ∩ 57 个 RED 节点 = 0”已独立复现。

## 数量口径问题

说明文件第二节写有“200 个节点，其中 105 个有边”，但直接从本提交的 116 条边表计算得到的端点并集为 104，且与 `route2_baseline_v1_nodes_104.csv` 和 `节点交集统计.txt` 一致。当前最终复核应采用可由文件重算的 **104**；“105”需要成员 3 说明是生成中间版本的统计，或在说明文件中修正，避免同时出现两个口径。

## 结论与状态

- 节点清单、边表和 RED 映射的交集复核完成，0 交集结果可靠。
- 接口字段和匹配逻辑的“数据范围不重叠”结论可以保留；这不等于两条路线已经完成真实数据命中接入。
- 当前仍有两项需要成员 3 配合澄清：脚本 SHA-256 登记不一致，以及说明文件中的 105/104 节点数量不一致。澄清前不应把五个文件写成“全部哈希一致”。
