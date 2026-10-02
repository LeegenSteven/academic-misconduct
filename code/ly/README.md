# ly — 李云

个人分析代码区。当前提交对应 2026-10-02 的本地分析版本；代码与数据快照分开保存，避免把本机路径或原始下载包带入仓库。

## 当前入口

| 脚本 | 用途 |
|---|---|
| `evaluate_scifact.py` | 按 SciFact 官方规则计算文档检索、证据句和标签指标 |
| `build_sciciteval_transfer.py` / `evaluate_sciciteval_transfer.py` | 构建并评估 SciCiteVal 跨数据集输入 |
| `build_sarol_retrieval.py` / `evaluate_sarol_transfer.py` | 构建 Sarol 检索候选并计算三分类指标 |
| `build_sarol_error_cases.py` / `evaluate_sarol_evidence_block_level.py` | 生成证据块级错误案例并评估证据块分类 |
| `compare_sarol_oracle_top20.py` | 对比 oracle 证据与 TF-IDF top-20 的公平结果 |
| `build_sarol_llm_format_pilot.py` | 生成大模型格式小样本验证材料 |
| `validate_member1_dev_contrast.py` | 校验成员 1 提供的 Dev 对照材料 |

大多数历史脚本都支持命令行路径参数；如果没有显式传入路径，不要假设仓库中存在本机历史目录。运行前先用 `python <script> --help` 查看参数。

## 当前数据快照

`data/processed/seed42_source_audit_ly_v19.csv` 是 seed=42 的 60 条来源核查脱敏快照：SciFact 30 条、ReferenceErrorDetection 30 条。它只保留版本/hash、引用文本、证据定位和李云侧 `annotator_2_*` 字段，不包含原始下载包，也不包含最终裁决字段。

## 环境

基础脚本使用 Python 3.10+；Sarol/SciCiteVal 转换脚本还需要 `numpy`、`scikit-learn`。原始数据获取和快照校验入口在 `scripts/`。
