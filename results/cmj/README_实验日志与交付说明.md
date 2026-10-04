# 陈明进 实验日志与交付说明

更新时间：2026-10-04

## 一、数据版本

| 数据集 | 行数 | SHA-256 |
|---|---:|---|
| claims-train.jsonl | 2141 | `43c2f9dc474e2d10c91da7b752407d04d31c77d5034a3920ad9db16c01058026` |
| claims-dev.jsonl | 316 | `6281a95a26b1111261d60599da67314d05b122b27b1e9dbb7d32623efb782414` |
| claims-test.jsonl | 606 | `b458c9ea7acb8630144652e732a846afdfac29230c20a61e402c628929890b50` |
| corpus.jsonl | 8515 | `59f2309e1124c9d2ef8240d9c725e1a9377ced43ae34a13f222c7c42d40d8167` |

数据路径：`Citation-Integrity-main/Data/multivers-format/`

## 二、训练（step2141 微调）

**运行命令：**
```bash
python run_task4_finetune.py
```

**主要参数：**
- 训练数据：claims-train.jsonl（2141条）
- 输入构造：有金标准证据用gold（1699条），无证据用BM25 top-20（442条）
- 标签分布：ACCURATE 1402 / NOT_ACCURATE 610 / IRRELEVANT 129
- 冻结策略：冻结前12层 + embeddings，可训练参数模块数270
- 训练步数：2141步（1 epoch）
- 模型：MultiVerS（Longformer-base）
- 设备：CPU
- 随机种子：未固定（训练完全复现受限，推理可复现）

**日志：** `task4_finetune/train_step2141.log`
**最终权重：** `task4_finetuned_full_step2141.pt`

## 三、Dev 评测（step2141）

**运行命令：**
```bash
python run_task4_eval_dev.py
```

**主要参数：**
- 评测数据：claims-dev.jsonl（316条）
- 检索：BM25 top-10
- 权重：step2141

**结果：**
- acc_sub（方案B，排除53条金标IRRELEVANT）= 0.6507（190/292）
- Macro-F1 = 0.6185
- ACCURATE: P=0.7419, R=0.7225, F1=0.7321, n=191
- NOT_ACCURATE: P=0.4952, R=0.5149, F1=0.5049, n=101

**日志：** `task4_finetune/dev_eval/dev_eval_step2141.log`

## 四、Test 评测（step2141，606条）

**运行命令：**
```bash
python run_task4_eval_test.py
```

**主要参数：**
- 评测数据：claims-test.jsonl（606条）
- 检索：BM25 top-10
- 权重：step2141
- Test只评一次，查看结果后未回头调参

**结果：**
- acc_sub（方案B，排除53条金标IRRELEVANT）= 0.6040（334/553）
- 整体acc = 0.5512（334/606）
- Macro-F1 = 0.3642
- ACCURATE: P=0.7409, R=0.6295, F1=0.6807, n=386
- NOT_ACCURATE: P=0.3297, R=0.5482, F1=0.4118, n=166
- IRRELEVANT: P=0, R=0, F1=0, n=52
- 混淆矩阵（行=gold，列=pred）：
  - ACCURATE → {ACC:243, NOT:143, IRR:0}
  - NOT_ACCURATE → {ACC:75, NOT:91, IRR:0}
  - IRRELEVANT → {ACC:10, NOT:42, IRR:0}
- 预测分布：NOT_ACCURATE 276 / ACCURATE 328 / NEI 2

**日志：** `task4_finetune/test_eval_step2141.log`
**预测文件：** `task4_finetune/test_predictions_step2141.jsonl`

## 五、NEI 两条说明

Test预测中有2条NEI（Not Enough Information）：

| claim_id | gold | pred | 原因 |
|---|---|---|---|
| 196 | NOT_ACCURATE | NEI | BM25 top-10未检索到有效证据，模型输入证据不足，输出NEI |
| 296 | IRRELEVANT | NEI | 原始数据evidence为空（{}），无证据可检索，模型输出NEI |

**统计方式：**
- NEI是MultiVerS模型在证据不足时的默认输出类别
- 金标准三分类为ACCURATE/NOT_ACCURATE/IRRELEVANT，不含NEI
- 计算准确率时，NEI预测与gold不一致，计为错误
- 方案B（acc_sub=0.6040）排除了53条金标IRRELEVANT，但这2条NEI的gold分别是NOT_ACCURATE和IRRELEVANT：
  - claim_id=196（gold=NOT_ACCURATE）计入分母，算错误
  - claim_id=296（gold=IRRELEVANT）在方案B中被排除，不计入分母

## 六、过采样实验（task3，2倍）

**运行命令：**
```bash
python run_task3_train_selfeval.py    # 第一步：Train自评找难样本
python run_task3_oversample2x.py      # 第二步：2倍过采样重训
```

**主要参数：**
- 难样本来源：仅Train（step2141自评，判错+低置信的歪曲样本）
- 难样本数：550条
- 重复倍数：2倍
- 过采样后训练量：2691条（2141 + 550）
- 其余训练配置与step2141完全一致（冻结策略、截断长度等）
- 红线确认：过采样样本全部来自Train，无Dev/Test样本

**结果（过采样后Dev step2691）：**
- acc_sub = 0.3459（101/292）
- Macro-F1 = 0.257
- NOT_ACCURATE召回 = 1.0（模型走捷径，全部判为NOT_ACCURATE）
- 整体预测分布：NOT_ACCURATE 316/316
- 结论：过采样无效，类别不平衡不能靠单纯重复样本解决

**样本清单：** `task3_oversample/task3_oversample2x_manifest_2026-09-23.json`
**日志：** `task3_oversample/dev_eval_after_oversample.log`

## 七、60条证据定位核对表

**文件：** `task2_evidence/task2_evidence_location_check_60_v3_2026-10-04.csv`

**结果：**
- locator_check（位置能否回到原文）：60/60 全部"是"
- evidence_valid（证据是否支持claim）：13是 / 47否 = 21.67%
- "证据不适用"与"定位错误"分开统计

## 八、口径说明

- 训练时无证据样本用BM25 **top-20** 构造输入
- Dev/Test评测统一用BM25 **top-10**
- 报告的Dev 0.6507和Test 0.604均为top-10评测结果
- 此处存在训练/评测检索深度不一致，已记录，后续复现需注意

## 九、复现限制

- 训练随机种子未固定，训练完全复现受限
- 推理（Dev/Test评测）可复现：固定权重+固定数据+固定检索参数
- 如需完全复现训练，需重新设置随机种子并重训
