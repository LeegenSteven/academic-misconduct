# RED 待补全文检索清单（2026-10-03）

## 目的

对 RED seed=42 中目前只有摘要或入口级定位的 10 条记录，检查是否存在可合法取得、能回到目标论文正文的公开全文。只有取得目标论文正文并记录页码/段落和文件哈希，才可提升为全文闸门通过；摘要、出版社入口、引用该 DOI 的其他论文和仅有仓储元数据均不计入。

## 检索结果

| citation_id | 被引 DOI | 公开全文检查 | 当前结论 |
|---|---|---|---|
| RED:3 | 10.1016/j.imbio.2021.152166 | OpenAlex 标为 closed；Semantic Scholar 未返回 OA PDF；PubMed/出版社页面为摘要或入口 | 待核，不能计入 |
| RED:7 | 10.2174/1574893615666200207094357 | Bentham 官方页面有摘要和购买入口；Semantic Scholar 未返回 OA PDF | 待核，不能计入 |
| RED:9 | 10.1016/j.gr.2010.02.011 | OpenAlex、Semantic Scholar 均未给出 OA 全文；ScienceDirect 仅有摘要入口 | 待核，不能计入 |
| RED:12 | 10.1038/345315a0 | OpenAlex、Semantic Scholar 均标为 closed；PubMed/机构页面只有摘要或书目信息 | 待核，不能计入 |
| RED:13 | 10.1002/eji.200737271 | Semantic Scholar 标为 closed；PubMed/机构页面未提供目标论文全文 PDF | 待核，不能计入 |
| RED:16 | 10.1016/j.lithos.2014.03.014 | Cardiff ORCA 条目明确写明该仓储不提供全文；OpenAlex 标为 closed | 待核，不能计入 |
| RED:22 | 10.1007/s10853-018-2793-3 | Springer/ResearchGate 仅可见摘要或预览；OpenAlex 标为 closed，未得公开 PDF | 待核，不能计入 |
| RED:25 | 10.1016/j.diamond.2008.01.033 | EPA HERO 只有元数据/摘要；OpenAlex 标为 closed，未得公开 PDF | 待核，不能计入 |
| RED:27 | 10.1002/anie.202016233 | Semantic Scholar 返回 Griffith handle；访问 Griffith DSpace 条目后仅发现 SWORD XML bitstream，未发现目标论文 PDF | 待核，不能计入 |
| RED:28 | 10.1063/1.4966192 | Semantic Scholar 未返回 OA PDF；出版社/索引页面未提供可复核正文 | 待核，不能计入 |

## 结论

本轮没有新增可通过全文闸门的记录；RED seed=42 的严格候选数仍为 16 条。不能把上述 10 条的摘要或入口定位改写成全文证据，也不能用同 DOI 的其他论文替代目标论文。

## 下一步

转入新的开放全文来源抽取自然引用候选。候选必须同时保存施引文献、被引文献、原始引用句、被引正文证据、许可、文件哈希和既有数据集去重结果；未完成双人盲标前只标为候选，不填写最终项目三分类。
