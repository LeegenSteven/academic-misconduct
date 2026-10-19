# SupervisedLogitsTrainer 显存优化方案补齐材料

**日期**：2026-10-19
**整理人**：陈明进
**状态**：材料已补齐，loss/梯度等价测试待 A100 运行

---

## 一、实际优化脚本及哈希

| 项目 | 路径 | SHA256 |
|---|---|---|
| 标准版训练脚本 | `code/cmj/route1_qwen38_train_sarol_v1.py` | `DFD4FFB58C613AD105D0D53B744920E44F5767563118C5830F2F664D0705DDE0` |
| 优化版训练脚本 | `code/cmj/route1_qwen38_train_sarol_memopt_v1.py` | `1DFFDCE3CC00C6957D8EB91D8C27C844E95F2FE4C8E5E157774A617614473D22` |

优化版核心类：`SupervisedLogitsTrainer(Trainer)`，重写 `compute_loss` 方法。

---

## 二、完整训练配置

两版共享的训练超参数（完全一致）：

| 参数 | 值 |
|---|---|
| 底座模型 | Qwen/Qwen3.8-27B (HF commit 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0) |
| 量化 | 4-bit QLoRA (nf4, bfloat16 compute, double_quant) |
| LoRA rank | 16 |
| LoRA alpha | 32 |
| LoRA dropout | 0.05 |
| target_modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| 学习率 | 1e-4 |
| optimizer | AdamW (weight_decay=0.0) |
| lr_scheduler | cosine (warmup_ratio=0.03) |
| micro_batch | 1 |
| gradient_accumulation | 16 |
| epochs | 1 |
| seed | 42 |
| bf16 | True |
| gradient_checkpointing | True (use_reentrant=False) |
| max_length | 5120 (冻结运行时；脚本默认4096，可通过--max-length覆盖) |
| 监督目标 | 仅 assistant 标签 JSON `{"label":"..."}` |
| 训练数据 | Sarol Train 2141 条 (v2 冻结) |
| 标签分布 | ACCURATE 1368 / NOT_ACCURATE 630 / IRRELEVANT 143 |

---

## 三、与原实现的差异表

| 维度 | 标准版 (Trainer) | 优化版 (SupervisedLogitsTrainer) |
|---|---|---|
| Trainer 类 | `transformers.Trainer` | 自定义 `SupervisedLogitsTrainer(Trainer)` |
| compute_loss | 模型内部 `forward()` 计算全序列 logits，labels 中 -100 位置自动 mask | 手动找出监督位置，用 `logits_to_keep=positions` 只计算这些位置的 logits |
| logits 形状 | `(batch, seq_len, vocab_size)` | `(batch, num_supervised_positions, vocab_size)` |
| 显存峰值 | 全序列 logits 需存储 `seq_len × vocab_size` 浮点 | 仅存储 `num_supervised × vocab_size`，assistant 标签仅约 10-20 token |
| loss 计算 | `F.cross_entropy(logits.view(-1, V), labels.view(-1), ignore_index=-100, reduction='mean')` | `F.cross_entropy(logits[0].float(), targets, reduction='mean')`，targets 已排除 -100 |
| next-token shift | 模型内部处理 (logits[t] 预测 labels[t+1]) | 手动处理：`positions = nonzero(labels[0, 1:] != -100)`，`targets = labels[0].index_select(0, positions+1)` |
| micro_batch 限制 | 任意 | 必须为 1 (代码中显式检查) |
| model_accepts_loss_kwargs | 默认 True | 设为 False (避免 Trainer 传入 num_items_in_batch 导致行为变化) |
| 输入处理 | labels 中 -100 为 padding/非监督位置 | 同左，positions 从 labels[0, 1:] 中提取非 -100 位置 |
| 梯度累积 | Trainer 原生处理，每 micro_batch loss 先除 accumulation_steps 再累积 | 同左，Trainer 原生处理不变 |
| 可训练参数 | 完全相同 (QLoRA 配置一致) | 完全相同 |
| 优化器/调度器 | 完全相同 | 完全相同 |

### 显存节省原理

标准 causal LM 训练中，logits 张量形状为 `(batch, seq_len, vocab_size)`。对于 Qwen3.8-27B，vocab_size=152064，seq_len=5120，单条样本的 logits 就需要 `1 × 5120 × 152064 × 2 bytes ≈ 1.5 GB`（bfloat16），加上反向传播的梯度缓存，峰值显存更高。

优化版只计算 assistant 标签位置的 logits（约 10-20 个 token），logits 张量降至 `1 × 15 × 152064 × 2 ≈ 4.5 MB`，显存节省约 99.7%。

---

## 四、官方 tokenizer 下全 Train 长度报告

**数据**：Sarol Train 2141 条 (v2 冻结)，Qwen3.8-27B 官方 tokenizer (trust_remote_code=True)

| 统计量 | 值 |
|---|---|
| 最小长度 | 741 |
| 最大长度 | 9475 |
| 平均长度 | 1340.7 |
| 中位数 | 1267 |
| P90 | 1626 |
| P95 | 1825 |
| P99 | 2709 |

### 分段分布

| 长度区间 | 条数 | 占比 |
|---|---|---|
| [0, 1024) | 162 | 7.6% |
| [1024, 2048) | 1917 | 89.5% |
| [2048, 3072) | 43 | 2.0% |
| [3072, 4096) | 9 | 0.4% |
| [4096, 5120) | 6 | 0.3% |
| [5120, ∞) | 4 | 0.2% |

### 超过 4096 的记录（10 条）

| 索引 | claim_id | 长度 | 标签 |
|---|---|---|---|
| 237 | 237 | 9295 | ACCURATE |
| 250 | 250 | 9475 | NOT_ACCURATE |
| 256 | 256 | 9435 | NOT_ACCURATE |
| 313 | 313 | 5712 | NOT_ACCURATE |
| 344 | 344 | 4257 | ACCURATE |
| 602 | 602 | 4792 | ACCURATE |
| 747 | 747 | 4948 | IRRELEVANT |
| 1338 | 1338 | 4791 | ACCURATE |
| 1341 | 1341 | 4111 | NOT_ACCURATE |
| 1344 | 1344 | 4788 | NOT_ACCURATE |

### 超过 5120 的记录（4 条，使用 max_length=5120 时会被截断）

| claim_id | 长度 | 标签 | 截断量 |
|---|---|---|---|
| 237 | 9295 | ACCURATE | 约 4175 token |
| 250 | 9475 | NOT_ACCURATE | 约 4355 token |
| 256 | 9435 | NOT_ACCURATE | 约 4315 token |
| 313 | 5712 | NOT_ACCURATE | 约 592 token |

> **注**：之前记录的"3 条超 4096（claim_id=237/250/256）"仅指超过 9000 的特别长记录。完整统计显示实际有 10 条超过 4096，其中 4 条超过 5120。使用 max_length=5120 时，这 4 条的候选证据部分会被截断，但 assistant 标签 JSON 在序列末尾，截断策略需确认是否保留标签。

---

## 五、loss 和可训练参数梯度对照（待 A100 运行）

### 测试方案

已编写等价性测试脚本 `code/cmj/test_supervised_logits_equivalence.py`（待创建），覆盖以下场景：

| 测试场景 | 说明 |
|---|---|
| next-token shift | 验证优化版的 positions+1 偏移与标准版的因果 shift 一致 |
| 变长标签 | 不同长度的 assistant 回复，验证 loss 计算范围一致 |
| padding | batch 内不同长度序列的 padding mask 处理 |
| 梯度累积 | 16 步累积后的总梯度与单步大 batch 梯度一致 |
| 最后不足一个累积周期 | 总样本数不能被 batch×accum 整除时，最后一步的梯度缩放 |
| 可训练参数梯度 | 两版对应 LoRA 参数的梯度在数值上一致 (rtol=1e-5, atol=1e-6) |
| loss 值 | 相同输入下两版 loss 值一致 (rtol=1e-5, atol=1e-6) |

### 运行要求

- 需要 A100 或同等 GPU（本地 RTX3050 4GB 无法加载 27B 模型）
- 需在李云的 A100 环境上运行，或由陈明进在有 GPU 的环境运行
- 测试使用小样本（3-5 条），完整梯度累积模拟需约 30 分钟

### 当前状态

- [x] 优化脚本已放入 `code/cmj/route1_qwen38_train_sarol_memopt_v1.py`
- [x] 脚本哈希已记录
- [x] 训练配置已整理
- [x] 与原实现差异表已整理
- [x] 全 Train 长度报告已完成
- [x] 超过 4096 的 10 条记录 ID 已列出
- [ ] 等价性测试脚本待编写
- [ ] 等价性测试待 A100 运行
- [ ] 4 条超 5120 记录的截断策略需确认（是否保留 assistant 标签）

---

## 六、checkpoint-100 选择依据

师兄确认：checkpoint 继续选 checkpoint-100，依据是 Sarol 本域 Dev 的既定 Macro-F1：

| checkpoint | Sarol Dev Macro-F1 |
|---|---|
| checkpoint-100 | 0.5996 |
| final | 0.5919 |

跨域结果作对照，不用后来的 Test 重新选点。

---

## 七、max_length=5120 的配置记录

- 冻结运行时使用 `max_length=5120`，完整保留输入（除 4 条超 5120 的记录外）
- 实际配置已记录在 `test_refreeze5120_run02/test_config_freeze.json`
- 脚本默认值为 4096，通过 `--max-length 5120` 参数覆盖
- 3 条超 9000 的记录（237/250/256）在 5120 下会被截断约 4000+ token，主要截断候选证据部分
