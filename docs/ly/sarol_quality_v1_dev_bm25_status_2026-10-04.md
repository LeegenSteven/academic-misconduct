# Sarol quality v1 Dev BM25 核验状态

李云侧已完成修复版数据接入和 Dev 检索覆盖核验。`build_sarol_retrieval.py` 现在直接读取 `claims-dev-model.jsonl`、`corpus.jsonl` 和显式 `gold`，不再依赖旧 `annotations.zip` 按顺序恢复标签。

主结果使用分组词法 BM25 top-10，候选限定为每条 claim 的 `cited_doc_ids` 对应的 abstract 句子。Dev 316 条中，证据句召回为 0.3484，证据文档召回为 0.6371，claim 级证据句召回为 0.5961，claim 级证据文档召回为 0.7373；空候选 0 条。

本结果是检索覆盖诊断，不是模型三分类评测。修复版 Train 重训后的模型预测尚未提供，因此三类 Precision、Recall、F1、Macro-F1 和混淆矩阵暂不生成；旧 checkpoint 结果只能作为旧实验对照，不能冒充修复版重训结果。

详见 [`results/ly/sarol_quality_v1_dev_bm25_v1/`](../../results/ly/sarol_quality_v1_dev_bm25_v1/)。
