# Sarol quality v1 Dev BM25 top 10

更新时间：2026-10-04
数据版本：`sarol-quality-v1`
数据提交：GitHub `main` `4453cc3`

## 输入

- `data/quality_v1/sarol/claims-dev-model.jsonl`：316 条 Dev claim；
- `data/quality_v1/sarol/corpus.jsonl`：8515 个 corpus 段落块；
- 标签直接读取 `claims[*].gold`，不再从旧 `annotations.zip` 恢复；
- 候选范围为每条 claim 的 `cited_doc_ids` 对应的全部 abstract 句子。

## 检索口径

本目录使用分组词法 BM25，参数 `k1=1.5`、`b=0.75`，主结果为 top-10。当前结果是可复现的检索覆盖诊断，不声称等同于 Pyserini 或 MonoT5 的完整官方管线。

## 结果

| 指标 | 数值 |
|---|---:|
| Dev claims | 316 |
| 显式标签分布 | ACCURATE 191 / NOT_ACCURATE 101 / IRRELEVANT 24 |
| 金标准证据句总数 | 597 |
| top-10 命中金标准证据句 | 208 |
| 证据句召回 | 0.3484 |
| 金标准证据文档总数 | 361 |
| top-10 命中金标准证据文档 | 230 |
| 证据文档召回 | 0.6371 |
| 有金标准证据的 claim | 255 |
| 至少命中一条金标准证据句 | 152 |
| claim 级证据句召回 | 0.5961 |
| 至少命中一个金标准证据文档 | 188 |
| claim 级证据文档召回 | 0.7373 |
| 空候选 claim | 0 |

## 文件

- `claims_dev_bm25_top10.jsonl`：不含 gold 的 BM25 top-10 候选句；
- `gold_mapping_dev.csv`：显式 gold 和金标准证据统计；
- `retrieval_metrics_top10.json`：检索指标；
- `manifest.json`：数据版本和处理口径；
- `run_log.md`：运行命令、校验和限制。

三分类模型指标不放在本目录中，因为本轮尚未取得使用修复版 Train 重新训练后的匹配预测文件。陈明进完成新 Train 重训和 Test 评测后，才能用对应预测计算三类 Precision、Recall、F1、Macro-F1 和混淆矩阵。
