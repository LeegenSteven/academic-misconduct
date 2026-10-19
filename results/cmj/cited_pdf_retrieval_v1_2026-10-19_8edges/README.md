# 8 条 PMC OA 引用边端到端检索结果

**日期**：2026-10-19
**Pipeline**：`code/cmj/route1_cited_pdf_retrieval_pipeline_v1.py`
**候选池**：`data/interim/pmc_oa_candidate_pool_ly_v3_2026-10-05.json`
**XML 源**：`data/raw/pmc_oa_v3_source_xml/`

## 引用边列表

| 引用边 | 施引 PMCID | 被引 PMCID | 被引文献主题 | 人工盲标 |
|---|---|---|---|---|
| V3-02 | PMC12900525 | PMC10765876 | AH-Plus/Bio-C/ADseal 根管封闭剂理化性质 | ACCURATE |
| V3-03 | PMC12900525 | PMC4868912 | 生物陶瓷根管封闭剂综述（黏附定义） | NOT_ACCURATE |
| V3-04 | PMC12900525 | PMC4841349 | 根管干燥度对封闭剂粘结强度影响 | ACCURATE |
| V3-05 | PMC13583542 | PMC13324970 | 丝氨酸八聚体与 α-羟基酸取代反应 | NOT_ACCURATE |
| V3-06 | PMC13583542 | PMC8876357 | α/β 氨基酸和羟基酸的差异寡聚化 | ACCURATE |
| V3-07 | PMC13583542 | PMC13193722 | D/L-2-羟基戊二酸发现手性依赖蛋白修饰 | ACCURATE |
| V3-09 | PMC13625197 | PMC7504301 | 透明质酸及其受体在神经系统中的多样作用 | ACCURATE |
| V3-10 | PMC13625197 | PMC10464498 | 生物制剂与衰老大脑：胶质炎症和神经毒性信号 | ACCURATE |

> 注：PMCID 以 manifest.json 和 locators.jsonl 为准，本表已修正。

## 盲标分布

- ACCURATE：6 条
- NOT_ACCURATE：2 条（V3-03 候选与 claim 直接矛盾；V3-05 候选方向与 claim 相反）

## 文件说明

- `cited_pdf_demo.inputs.jsonl`：模型输入（claim + user_prompt + 10 条 BM25 候选证据）
- `cited_pdf_demo.locators.jsonl`：候选证据定位（evidence_id、原文、页/段位置）
- `blind_annotation_cmj.jsonl`：陈明进人工盲标结果（reviewer=cmj, review_status=blind_annotation_completed）

- `cited_pdf_demo.manifest.json`：源文件哈希、检索配置、统计与"无 gold（待盲标）"声明
- A100 推理待李云执行，推理完成后与人工盲标做一致性比对。
