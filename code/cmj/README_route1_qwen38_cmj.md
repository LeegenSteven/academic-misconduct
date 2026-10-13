# 路线一 Qwen3.8-27B QLoRA 微调 — 陈明进交付

## 概述

本目录包含路线一Qwen3.8-27B QLoRA微调的陈明进负责部分：训练脚本、评测脚本、被引全文检索模块、adapter推理服务、部署指南。

## 文件清单

| 文件 | 说明 |
|---|---|
| `route1_qwen38_train_sarol_v1.py` | Sarol adapter（Mbio）训练脚本，4-bit QLoRA，只监督label JSON |
| `route1_qwen38_eval_v1.py` | 推理评测脚本，支持M0/Mbio/Mscv，输出三类P/R/F1+Macro-F1+混淆矩阵 |
| `route1_qwen38_fulltext_retriever_v1.py` | 被引全文解析与BM25检索模块（PDF/XML→句段→位置映射→检索） |
| `route1_qwen38_service_v1.py` | adapter推理服务，支持底座+两个adapter切换 |
| `ROUTE1_QWEN38_DEPLOY_GUIDE.md` | A100部署指南（环境、依赖、路径修改、运行命令） |

## 训练配置

| 参数 | 值 |
|---|---|
| 底座模型 | 官方 Qwen/Qwen3.8-27B |
| 量化 | 4-bit NF4 |
| LoRA rank | 16 |
| LoRA alpha | 32 |
| LoRA dropout | 0.05 |
| 学习率 | 1e-4 |
| micro-batch | 1（A100可调到4-8） |
| 梯度累积 | 16 |
| 最大长度 | 4096 tokens |
| 随机种子 | 42 |
| 监督目标 | 只监督 `{"label":"ACCURATE"}`，屏蔽system/user/padding的loss |
| target_modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |

## 数据

Sarol数据使用quality_v1版本，BM25 top-10输入由李云构建：
- Train: 2141条（ACCURATE 1368 / NOT_ACCURATE 630 / IRRELEVANT 143）
- Dev: 316条（ACCURATE 191 / NOT_ACCURATE 101 / IRRELEVANT 24）
- Test: 606条（ACCURATE 386 / NOT_ACCURATE 170 / IRRELEVANT 50）

输入长度：p50≈950 tokens，p99≈1500 tokens，max≈4000 tokens，4096无截断。

## 快速开始（A100）

```bash
# 1. 安装依赖
pip install torch transformers peft bitsandbytes accelerate rank_bm25 pymupdf

# 2. 修改脚本中的路径（MODEL_PATH, SAROL_INPUT_DIR, SAROL_GOLD_DIR, OUTPUT_DIR）

# 3. 冒烟测试（32条）
python route1_qwen38_train_sarol_v1.py --smoke

# 4. 正式训练（1 epoch）
python route1_qwen38_train_sarol_v1.py --epochs 1

# 5. Dev评测
python route1_qwen38_eval_v1.py --split dev --model_name M0
python route1_qwen38_eval_v1.py --split dev --adapter /path/to/final_adapter --model_name Mbio

# 6. Test评测
python route1_qwen38_eval_v1.py --split test --model_name M0
python route1_qwen38_eval_v1.py --split test --adapter /path/to/final_adapter --model_name Mbio
```

## 输出说明

训练输出：
- `final_adapter/` — adapter权重（PeftModel可直接加载）
- `training_config.json` — 完整训练配置
- `checkpoint-*/` — 中间checkpoint

评测输出：
- `{model}_{split}_predictions.jsonl` — 逐条预测（claim_id, gold, pred, raw_output）
- `{model}_{split}_metrics.json` — 指标（accuracy, macro_f1, 三类P/R/F1, 混淆矩阵）

## 被引全文检索模块使用

```python
from route1_qwen38_fulltext_retriever_v1 import FullTextRetriever

retriever = FullTextRetriever()
retriever.parse_pdf("cited_paper.pdf")  # 或 parse_xml("cited_paper.json")
results = retriever.search("查询文本", top_k=10)
# 返回：rank, score, sentence_id, text, page, paragraph, char_start, char_end
```

## 注意事项

1. **GPU显存**：27B模型4-bit QLoRA训练需要≥16GB显存，RTX 3050 4GB无法训练，需A100
2. **路径配置**：脚本中路径为本地硬编码，A100运行前需修改
3. **监督目标**：只监督assistant输出的`{"label":"..."}`，不监督reason/evidence_ids
4. **Test只跑一次**：冻结checkpoint后统一跑Test，不根据Test表现调参
5. **证据不足不判IRRELEVANT**：检索没找到支持时label=null+待核原因

## 待完成（需A100）

- [ ] 32条冒烟训练跑通
- [ ] Sarol adapter正式训练（1 epoch）
- [ ] M0/Mbio Dev评测
- [ ] M0/Mbio Test评测
- [ ] adapter服务加载验证
- [ ] 与李云的Mscv交叉评测
