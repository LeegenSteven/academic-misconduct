# Sarol quality v1 Dev BM25 top 10 运行记录

日期：2026-10-04
执行人：李云
仓库提交：`4453cc374846fff63edd87849472a6ae72173c10`
数据版本：`sarol-quality-v1`

## 命令

```bash
python scripts/validate_sarol_training.py
python code/ly/build_sarol_retrieval.py \
  --data data/quality_v1/sarol \
  --split dev \
  --top-k 10 \
  --output results/ly/sarol_quality_v1_dev_bm25_v1
```

## 校验结果

`validate_sarol_training.py` 通过：Train 2141、Dev 316、Test 606，corpus 8515 个段落块，证据句引用 6134 条。

## 处理口径

- 标签直接读取修复版 claim 的显式 `gold`；没有读取旧 `annotations.zip`；
- 候选限定为每条 claim 的 `cited_doc_ids`，再对其中所有 abstract 句子做分组词法 BM25；
- 参数：`k1=1.5`、`b=0.75`；
- 主结果：BM25 top-10；
- 空候选仍保留在 claim 总数中；
- 本目录只报告检索覆盖，不把检索结果伪装成模型三分类预测；
- 没有修复版 Train 重训后的模型预测，因此暂不计算修复版模型的三类指标。

## 主要结果

Dev 316 条，显式标签为 ACCURATE 191、NOT_ACCURATE 101、IRRELEVANT 24。top-10 证据句召回为 0.3484，证据文档召回为 0.6371，claim 级证据句召回为 0.5961，claim 级证据文档召回为 0.7373，空候选为 0 条。

## 限制

这是仓库内可复现的分组词法 BM25 诊断，不能写成 Pyserini 或 MonoT5 的完整官方管线结果。三分类 Precision、Recall、F1、Macro-F1 和混淆矩阵需等陈明进用修复版 Train 重训并提供匹配预测后再计算。
