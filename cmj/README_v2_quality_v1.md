# 陈明进 - MultiVerS 微调与评测脚本（quality_v1 修复版数据）

## v2 版脚本（2026-10-08）

针对师兄上传的修复版 Sarol 数据（quality_v1），对原脚本进行了以下修改：

### 1. 数据路径切换
- 训练数据：`data/quality_v1/sarol/claims-train-model.jsonl`（2141条）
- 验证数据：`data/quality_v1/sarol/claims-dev-model.jsonl`（316条）
- 测试数据：`data/quality_v1/sarol/claims-test-model.jsonl`（606条）
- 语料库：`data/quality_v1/sarol/corpus.jsonl`（8515段落块）

### 2. IRRELEVANT / NEI 标签映射修复
- **修复前**：评测脚本 `LABEL_LOOKUP = {0: "NOT_ACCURATE", 1: "NEI", 2: "ACCURATE"}`
- **修复后**：`LABEL_LOOKUP = {0: "NOT_ACCURATE", 1: "IRRELEVANT", 2: "ACCURATE"}`
- 训练脚本 `LABEL2ID` 原本就是正确的：`{"NOT_ACCURATE": 0, "IRRELEVANT": 1, "ACCURATE": 2}`

### 3. 无检索候选单独记录为弃权
- **修复前**：BM25 未返回有效候选时，预测直接赋值为 `LABEL_LOOKUP[1]`（即 NEI）
- **修复后**：无检索候选预测标记为 `ABSTAIN`（弃权），计入评测分母，不参与分类预测
- 评测输出中 `n_abstain` 字段记录弃权样本数

### 4. BM25 口径统一
- **修复前**：训练用 BM25 top-20，评测用 BM25 top-10（train-test mismatch）
- **修复后**：训练和评测统一使用 BM25 top-10

### 5. 评测指标改为三分类全量
- **修复前**：Dev 评测只计算 ACCURATE 和 NOT_ACCURATE 两类（排除 IRRELEVANT），即"方案B"
- **修复后**：Dev 和 Test 均计算三分类全量指标（包含 IRRELEVANT），弃权样本计入分母
- 输出包含：各类 P/R/F1、Macro-F1、整体 Accuracy、混淆矩阵（行=gold，列=pred，含 ABSTAIN 列）

## 文件说明

| 文件 | 用途 |
|------|------|
| `run_task4_finetune_v2.py` | 修复版数据训练脚本 |
| `run_task4_eval_dev_v2.py` | 修复版数据 Dev 评测脚本 |
| `run_task4_eval_test_v2.py` | 修复版数据 Test 评测脚本 |

## 使用方法

```bash
# 训练（smoke test 32条）
python run_task4_finetune_v2.py --smoke

# 训练（full 2141条）
python run_task4_finetune_v2.py --full

# Dev 评测（默认加载 task4_v2_finetuned_full_step2141.pt）
python run_task4_eval_dev_v2.py

# Dev 评测（指定 checkpoint）
python run_task4_eval_dev_v2.py /path/to/checkpoint.pt

# Test 评测
python run_task4_eval_test_v2.py
python run_task4_eval_test_v2.py /path/to/checkpoint.pt
```

## 数据版本说明

修复版数据修正了旧转换中 39 条标签错配（Train 36条、Test 3条，Dev不变）：
- Test 类别变化：ACCURATE 386 / NOT_ACCURATE 170 / IRRELEVANT 50
- 旧版 Test：ACCURATE 386 / NOT_ACCURATE 166 / IRRELEVANT 52（4条从 IRRELEVANT 改为 NOT_ACCURATE）
- 官方 Train/Dev/Test 划分保持不变

## 旧版脚本（v1，错配标签数据，保留对照）

- `run_task4_finetune.py` / `run_task4_eval_dev.py` / `run_task4_eval_test.py`
- 使用旧的 `converted-three-class-v2` 数据，存在 39 条标签错配
- 旧实验结果保留用于对照，不再用于正式结论
