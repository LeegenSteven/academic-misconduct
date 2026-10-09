# 陈明进 - MultiVerS 微调与评测（quality_v1 修复版数据）

## 概述

针对师兄上传的修复版 Sarol 数据（quality_v1，修正39条标签错配），用新Train重新训练MultiVerS，在Dev上验证后评测全部606条Test。

## v2 版脚本修改（2026-10-08）

### 1. 数据路径切换到 quality_v1
- 训练：`data/quality_v1/sarol/claims-train-model.jsonl`（2141条）
- 验证：`data/quality_v1/sarol/claims-dev-model.jsonl`（316条）
- 测试：`data/quality_v1/sarol/claims-test-model.jsonl`（606条）
- 语料库：`data/quality_v1/sarol/corpus.jsonl`（8515段落块）

### 2. IRRELEVANT / NEI 标签映射修复
- **修复前**：评测脚本 `LABEL_LOOKUP = {0: "NOT_ACCURATE", 1: "NEI", 2: "ACCURATE"}`
- **修复后**：`LABEL_LOOKUP = {0: "NOT_ACCURATE", 1: "IRRELEVANT", 2: "ACCURATE"}`
- 训练脚本 `LABEL2ID` 原本正确：`{"NOT_ACCURATE": 0, "IRRELEVANT": 1, "ACCURATE": 2}`

### 3. 无检索候选单独记录为弃权
- **修复前**：BM25未返回有效候选时，预测直接赋值为 `LABEL_LOOKUP[1]`（即NEI）
- **修复后**：无检索候选预测标签为 `ABSTAIN`（弃权），计入评测分母，不参与分类预测
- 评测输出中 `n_abstain` 字段记录弃权样本数

### 4. BM25 口径统一
- **修复前**：训练用 BM25 top-20，评测用 BM25 top-10（train-test mismatch）
- **修复后**：训练和评测统一使用 BM25 top-10

### 5. 评测指标改为三分类全量
- **修复前**：Dev评测只计算ACCURATE和NOT_ACCURATE两类（排除IRRELEVANT），即"方案B"
- **修复后**：Dev和Test均计算三分类全量指标（包含IRRELEVANT），弃权样本计入分母
- 输出包含：各类P/R/F1、Macro-F1、整体Accuracy、混淆矩阵（行=gold，列=pred，含ABSTAIN列）

### 6. GPU支持
- 自动检测CUDA，模型和数据移到GPU
- 训练速度：GPU约0.8条/s（CPU约0.07条/s，快约12倍）

## 运行命令

### 训练
```bash
python run_task4_finetune_v2.py --full
# smoke test: python run_task4_finetune_v2.py --smoke
```

### Dev验证
```bash
python run_task4_eval_dev_v2.py
```

### Test评测
```bash
python run_task4_eval_test_v2.py
```

## 训练配置

- 模型：MultiVerS（allenai/multivers）
- 冻结：前12层 + embeddings
- 学习率：1e-5
- batch size：1，gradient accumulation：8
- MAX_LEN：384
- BM25：top-10（训练和评测统一）
- 训练步数：2141步（每步1条样本）
- checkpoint：每250步保存
- 设备：CUDA（RTX 3050 Laptop 4GB）
- 环境：torch 2.5.1+cu121, transformers 4.46.0, Python 3.9

## 修复版数据标签分布

| 数据集 | ACCURATE | NOT_ACCURATE | IRRELEVANT | 总计 | evidence_missing |
|--------|----------|--------------|------------|------|-------------------|
| Train | 1368 | 630 | 143 | 2141 | 442 |
| Dev | 191 | 101 | 24 | 316 | 61 |
| Test | 386 | 170 | 50 | 606 | 119 |

修正39条标签错配：Train 36条、Test 3条，Dev不变。

## Dev 316 结果（BM25 top-10，三分类全量）

- 整体Acc：**0.4968**（157/316）
- Macro-F1：**0.413**
- 弃权：0条

| 类别 | Precision | Recall | F1 | 数量 |
|------|-----------|--------|-----|------|
| ACCURATE | 0.812 | 0.361 | 0.500 | 191 |
| NOT_ACCURATE | 0.373 | **0.842** | 0.517 | 101 |
| IRRELEVANT | 1.000 | 0.125 | 0.222 | 24 |

### Dev 混淆矩阵（行=gold，列=pred）

| gold\pred | ACCURATE | NOT_ACCURATE | IRRELEVANT | ABSTAIN |
|-----------|----------|--------------|------------|---------|
| ACCURATE | 69 | 122 | 0 | 0 |
| NOT_ACCURATE | 16 | 85 | 0 | 0 |
| IRRELEVANT | 0 | 21 | 3 | 0 |

预测分布：NOT_ACCURATE 228, ACCURATE 85, IRRELEVANT 3

## Test 606 结果（BM25 top-10，三分类全量）

- 整体Acc：**0.4257**（258/606）
- Macro-F1：**0.3385**
- 弃权：0条

| 类别 | Precision | Recall | F1 | 数量 |
|------|-----------|--------|-----|------|
| ACCURATE | 0.793 | 0.288 | 0.422 | 386 |
| NOT_ACCURATE | 0.312 | **0.841** | 0.455 | 170 |
| IRRELEVANT | 0.500 | 0.080 | 0.138 | 50 |

### Test 混淆矩阵（行=gold，列=pred）

| gold\pred | ACCURATE | NOT_ACCURATE | IRRELEVANT | ABSTAIN |
|-----------|----------|--------------|------------|---------|
| ACCURATE | 111 | 271 | 4 | 0 |
| NOT_ACCURATE | 27 | 143 | 0 | 0 |
| IRRELEVANT | 2 | 44 | 4 | 0 |

预测分布：NOT_ACCURATE 458, ACCURATE 140, IRRELEVANT 8

## 相对旧实验的变化

### 旧实验（错配标签数据）
- Dev：acc=0.6507, macro_f1=0.6185, NOT_ACCURATE召回=0.5149（二分类，排除IRRELEVANT）
- Test：方案B acc=0.6040, 全量acc=0.5512, macro_f1=0.3642, NOT_ACCURATE召回=0.5482
- Test NEI 2条：claim_id=196（gold=NOT_ACCURATE）、claim_id=296（gold=IRRELEVANT）

### 新实验（修复版数据）
- Dev：acc=0.4968, macro_f1=0.413, NOT_ACCURATE召回=0.8416（三分类全量）
- Test：acc=0.4257, macro_f1=0.3385, NOT_ACCURATE召回=0.8412（三分类全量）
- 弃权：0条（NEI问题已修复，无检索候选记ABSTAIN）

### 关键变化
1. **NOT_ACCURATE召回大幅提升**：从0.55→0.84，歪曲引用检出能力增强
2. **整体Acc下降**：从0.55→0.43，主因是标签修正后类别不平衡更严重，模型偏向预测NOT_ACCURATE
3. **IRRELEVANT略有改善**：召回从0→0.08，但仍几乎学不会
4. **NEI问题消除**：旧版Test有2条NEI，新版弃权0条
5. **指标口径统一**：从二分类（方案B）改为三分类全量，结果更完整

### 问题分析
- 模型严重偏向预测NOT_ACCURATE（Test中76%判为NOT_ACCURATE）
- ACCURATE召回低（29%），大量ACCURATE被误判为NOT_ACCURATE
- IRRELEVANT训练样本少（Train仅143条，占6.7%），模型难以学会
- 下一步可考虑类别加权或输出层调整

## 文件清单

### 脚本（code/cmj/）
- `code/cmj/run_task4_finetune_v2.py` - 训练脚本（quality_v1数据 + BM25 top-10 + GPU支持）
- `code/cmj/run_task4_eval_dev_v2.py` - Dev评测脚本（NEI→IRRELEVANT修复 + ABSTAIN + 三分类全量）
- `code/cmj/run_task4_eval_test_v2.py` - Test评测脚本（同上 + 输出逐条预测jsonl）

### 日志与结果（results/cmj/task4_finetune_v2/）
- `task4_v2_finetune_full_gpu_2026-10-08.log` - full训练日志（GPU）
- `task4_v2_dev_eval_task4_v2_finetuned_full_step2141_2026-10-08.json` - Dev评测结果
- `task4_v2_test_eval_task4_v2_finetuned_full_step2141_2026-10-08.json` - Test评测结果
- `task4_v2_test_predictions_task4_v2_finetuned_full_step2141.jsonl` - Test逐条预测（606条）

### 模型
- 最终模型：`task4_v2_finetuned_full_step2141.pt`（1.6GB，因体积过大未上传GitHub，本地保存）

## 注意事项

1. 脚本中数据路径为硬编码绝对路径，使用前需修改 `QUALITY_V1` 变量
2. 模型文件1.6GB未上传GitHub，需重新训练或从本地获取
3. 训练随机种子未固定，结果可复现性有限；推理结果可复现
4. BM25使用rank_bm25库，需安装：`pip install rank_bm25`
