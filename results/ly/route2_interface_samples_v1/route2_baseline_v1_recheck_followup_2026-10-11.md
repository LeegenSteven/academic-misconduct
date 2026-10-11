# route2_baseline_v1 复核跟进（2026-10-11）

成员 3 回复后，我重新读取其仓库最新提交 `bc3b4fd98ea5176c59e85c96d49dd25dda9c0e79`：

<https://github.com/citation-integrity-lab/citation-integrity-lab/tree/bc3b4fd98ea5176c59e85c96d49dd25dda9c0e79>

## 已解决

说明文件已经把“200 个节点，其中 105 个有边”改为“200 个节点，其中 104 个有边”，与以下文件的独立重算一致：

- `final_edges_no_selfcite.csv`：116 条边，端点并集 104 个节点；
- `route2_baseline_v1_nodes_104.csv`：104 个唯一节点；
- `red_doi_to_w_mapping.csv`：30 条 RED 映射，57 个唯一节点；
- 两种路线二节点集合与 RED 节点集合的交集均为 0。

## 仍需修正

说明文件目前登记 `run_cidre_on_openalex.py` 的 SHA-256 为：

`db620f0ee41ec03662b04ef6ac250277b745ce02d84282cfe311cfaf31cd45fb`

但在该最新提交中，直接对 Git blob 计算得到的实际 SHA-256 仍为：

`e781d3119632992a42511e394998830a09b7ccc40441e2fdeb84a31c740108fd`

因此脚本哈希仍未闭合。当前脚本内容中的 `API_KEY` 已为空，未发现明文密钥；待成员 3 确认后，应把说明文件改成实际 blob 哈希，或把仓库脚本更新为与 `db620f0e...` 对应的版本，再重新登记。

完整核验表见 [`route2_baseline_v1_hash_verification_followup_2026-10-11.csv`](route2_baseline_v1_hash_verification_followup_2026-10-11.csv)。

## 当前结论

节点统计和 0 交集结论已经确认；五个文件的哈希尚不能全部标记为一致，脚本哈希仍是唯一待确认项。
