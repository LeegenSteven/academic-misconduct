# ly — 李云

个人分析代码区。当前提交对应 2026-10-02 的本地分析版本；代码与数据快照分开保存，避免把本机路径或原始下载包带入仓库。

## 当前入口

| 脚本 | 用途 |
|---|---|
| `evaluate_scifact.py` | 按 SciFact 官方规则计算文档检索、证据句和标签指标 |
| `build_sciciteval_transfer.py` / `evaluate_sciciteval_transfer.py` | 构建并评估 SciCiteVal 跨数据集输入 |
| `build_sarol_retrieval.py` / `evaluate_sarol_transfer.py` | 从 `sarol-quality-v1` 构建 BM25 检索候选；有匹配模型预测时再计算三分类指标 |
| `build_sarol_error_cases.py` / `evaluate_sarol_evidence_block_level.py` | 生成证据块级错误案例并评估证据块分类 |
| `compare_sarol_oracle_top20.py` | 对比 oracle 证据与 TF-IDF top-20 的公平结果 |
| `build_sarol_llm_format_pilot.py` | 生成大模型格式小样本验证材料 |
| `validate_member1_dev_contrast.py` | 校验成员 1 提供的 Dev 对照材料 |

大多数历史脚本都支持命令行路径参数；如果没有显式传入路径，不要假设仓库中存在本机历史目录。运行前先用 `python <script> --help` 查看参数。

## 修复版 Sarol Dev 检索

`build_sarol_retrieval.py` 已改为直接读取 `data/quality_v1/sarol/` 下的 `claims-{split}-model.jsonl`、`corpus.jsonl` 和显式 `gold`，不再从旧 `annotations.zip` 恢复标签。默认 Dev 输出为按每条 claim 的 `cited_doc_ids` 限定候选句的分组词法 BM25 top-10：

```bash
python code/ly/build_sarol_retrieval.py --data data/quality_v1/sarol --split dev --top-k 10 --output results/ly/sarol_quality_v1_dev_bm25_v1
```

该脚本只报告证据句/文档召回和候选覆盖。三分类 Precision、Recall、F1、Macro-F1 和混淆矩阵必须使用同一数据版本对应的模型预测，再运行 `evaluate_sarol_transfer.py`；不能用旧 checkpoint 的预测冒充修复版 Train 重训结果。当前实现是仓库内可复现的分组词法 BM25 诊断，不声称等同于 Pyserini 或 MonoT5 的完整官方管线。

本轮 Dev 结果见 [`sarol_quality_v1_dev_bm25_v1`](../results/ly/sarol_quality_v1_dev_bm25_v1/)。

## 当前数据快照

`data/processed/seed42_source_audit_ly_v19.csv` 是 seed=42 的 60 条来源核查脱敏快照：SciFact 30 条、ReferenceErrorDetection 30 条。它只保留版本/hash、引用文本、证据定位和李云侧 `annotator_2_*` 字段，不包含原始下载包，也不包含最终裁决字段。

## 环境

基础脚本使用 Python 3.10+；Sarol/SciCiteVal 转换脚本还需要 `numpy`、`scikit-learn`。原始数据获取和快照校验入口在 `scripts/`。
