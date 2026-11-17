# Mbio 复现核验审计（audit.md）

- 日期：2026-10-24
- 责任人：陈明进（本地CPU侧复核与归档）
- 范围：Sarol 路线一 Mbio 复现。本文档汇总「10/17 实际训练文件哈希对照」「Train2141 长度/监督 token 复算」「损失/梯度等价性（CPU 侧结论）」「checkpoint 来源与恢复索引」四部分，并登记缺口。

## 0. 结论速览

| 项 | 结论 | 证据位置 |
|---|---|---|
| 10/17 实际训练文件哈希 | 6/6 与交接包 manifest 一致 | 本文件 §1 |
| Train2141 长度复算 | ALL_PASS（2141 条、3 条超 4096、最大 4924、5120 下 0 超长、监督 token 20042） | 本文件 §2 + `length_report/` |
| 损失/梯度等价性（CPU 侧） | 李云 2026-10-20 回传实测通过（5 正向场景 + 1 负例对照） | 本文件 §3 + `equivalence_test/` |
| checkpoint 来源 | checkpoint-100 为冻结候选（Sarol Dev Macro-F1 0.5996 > final 0.5919） | 本文件 §4 + `adapter_recovery/` |

**边界声明**：CPU 侧等价性通过只支持「修复候选的目标与更新逻辑」正确，**不证明 27B/NF4 逐位等价，不把历史 adapter 写成已自动修复**。27B/NF4 GPU 验证与 checkpoint 保存/重载验证待 A100 执行（见 §5）。

## 1. 10/17 实际训练文件哈希对照

对照对象：本地 `results/route1_qwen38_v2/2026-10-15/sarol/` 与交接包 `deliverables/2026-10-17_Mbio代跑交接/Mbio代跑交接_20261017/evidence/manifest.json`。

| 文件 | 本地 SHA256 | manifest | 结果 |
|---|---|---|---|
| train.inputs.jsonl | 712338b41e7f1b56b8a4cb8a75018a57bab89706ed0b6d9f4a2e7dc8bd0d0180 | 一致 | OK |
| train.gold.jsonl | f245b94aafc67934b43c760a1d6c68b0f1042d7561f493280c77d49467c1fad8 | 一致 | OK |
| 交接包 train.log | 5535f548da347019423f2ec44ab4d9b9738433173a8686c03bafbf72201bdaa4 | 一致 | OK |
| 交接包 training_config.json | f468c2cc6c7c16098c814a106db8eb0f44f235228a5b5ee5802a0d1518328d42 | 一致 | OK |
| 交接包 smoke/reload.log | c18b9ad9d9a9601b9170cd4043820f4ae29c865597c2cda2c36bce1a2c222000 | 一致 | OK |
| 交接包 smoke/train.log | fa36272ddf2ebc64b1745e3bbef4bc7f9f0c6a0fca7d464842f64cbedaa96407 | 一致 | OK |

脚本哈希对照：

| 脚本 | SHA256 | 说明 |
|---|---|---|
| code/cmj/route1_qwen38_train_sarol_memopt_v1.py（修复后在用） | 9A47A2DAA2C92B19D6274E26B526075A5402406E3DE068852585FF32818E4ABA | 与李云 CPU 包 bundle 内一致 |
| code/cmj/test_supervised_logits_equivalence.py（更新后） | AE0F122C1DB46ABCC97060799DA298849814888A93646ED756529D8759481F10 | 与李云 CPU 包 bundle 内一致 |
| code/cmj/route1_qwen38_train_sarol_v1.py（标准版） | DFD4FFB58C613AD105D0D53B744920E44F5767563118C5830F2F664D0705DDE0 | 训练标准实现 |
| 10/17 实际训练脚本（交接包 artifacts/code/route1_qwen38_train_sarol_memopt_trial_20261017.py） | 1DFFDCE3CC00C6957D8EB91D8C27C844E95F2FE4C8E5E157774A617614473D22 | = 李云 CPU 包修复前 before_fix 对照 |
| 10/17 test_trial（交接包） | 1AFAB4355FB75F03C346B3C616EDE075E10000822890EB7AB45CFDFB41C597F9 | 10/17 实测用测试脚本 |

## 2. Train2141 长度与监督 token 复算

- 口径：官方 Qwen3.8-27B tokenizer（`C:\Users\Administrator\Documents\models\Qwen3.8-27B`，18 分片完整）+ `shared.route1_qwen38.data_contract.encode_assistant_record`（apply_chat_template、字符偏移 mask、EOS 监督、5120 超长显式报错），逐条复算，非文本拼接估算。
- 结果（全部通过，`all_pass=true`）：
  - 样本数 2141；min 508 / max 4924 / mean 824.39 / median 787
  - 超 4096 仅 3 条：claim_id 237（4789, ACCURATE）、250（4924, NOT_ACCURATE）、256（4866, NOT_ACCURATE）
  - 5120 上限下 0 条超长（未截断、未漏样本）
  - 监督 token 合计 20042；EOS 被监督样本 2141/2141；编码失败 0
  - 标签分布：ACCURATE 1368 / NOT_ACCURATE 630 / IRRELEVANT 143
- 与 10/17 交接记录吻合：3 条超 4096、最大 4924、5120 未截断、监督 token 20042。
- 输出：`length_report/sarol_train2141_length_recount_20261024.json`；复算脚本 `code/recount_train2141_lengths_20261024.py`。
- 注意：本口径（官方 tokenizer + chat_template 实际编码）与 2026-10-19 旧报告 `sarol_train_length_report_v2.json`（文本拼接估算口径，max 9475）不同，旧文件仅作历史材料，勿混用。

## 3. 损失/梯度等价性（CPU 侧结论，李云 2026-10-20 回传）

李云 CPU 等价性修复实测包结论：**通过**（5 个正向场景 + 1 个预期失败对照全过）：

- 五个修复场景（loss 归一化）梯度与更新后参数最大差均为 0；
- loss 最大绝对差 9.5367431640625e-7（atol=1e-6 / rtol=1e-5，未放宽）；
- 负例（旧归一化版本）被正确拒绝：scaled loss 最大差约 0.163931、梯度约 1.69e-4、参数约 3.38e-4。

A100 环境：Python 3.13.12、torch 2.11.0+cu130、transformers 5.8.0、PEFT 0.21.2、accelerate 1.14.0、datasets 5.0.0。

**限制（李云原文口径）**：CPU 通过只支持修复候选目标/更新逻辑，不证明 27B/NF4 逐位等价、不把历史 adapter 写成已自动修复。

## 4. checkpoint 来源与选择依据

- A100 路径：`/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/cmj_sarol_mbio_full_memopt_trial_20261017_gpu2/train/`
- checkpoint-100/adapter_model.safetensors SHA256：`0f4019af9d0f510408f841797c1038bb19abfee8b6e5f24dc7f222501776bd09`
- final_adapter 权重视为目录整体 SHA256：`9f03dccc3627c07fc021093f9a2ce6df027444d9ea0421b5d1e21223b75d18e8`
- 两份 adapter_config.json 同 SHA256：`b425bcd6ba101d02dcb1dd8d9f892b315bd082a7b6feeba938b43bc58aedc2f8`
- 选择依据：Sarol Dev Macro-F1 checkpoint-100 **0.599595 > final 0.591875**（final 在 Sarol 多对 3 但 NA 召回降），checkpoint-100 为冻结候选。
- 恢复索引与重载命令：见 `adapter_recovery/`。

## 5. 缺口与待办

1. **27B/NF4 GPU 验证**：修复候选在 A100 上重跑等价性测试（本地 RTX3050 4GB 无法执行）。已整理 GPU 验证请求包（桌面《给李云_GPU等价性验证与保存重载_20261024.zip》或仓库 `deliverables/2026-10-24_GPU验证请求_李云/`），待李云执行回传。
2. **checkpoint 保存/重载验证**：GPU 侧独立进程加载 final_adapter/checkpoint-100 做推理（参照 10/17 smoke reload 流程）。一并放入 GPU 验证请求包。
3. 10/25 联合验收：acceptance.csv、README（李云汇总）、一页联合结论未做；正式端到端验收计数为 0（18 点实际尝试，第 1/15 暂缓，20 点分母不变）。
4. 归档是否 push GitHub 待用户安排（按惯例 CSV+md 走 GitHub、回复走微信）。

## 6. 目录对照（任务书 E5 交付项）

| 任务书要求 | 位置 |
|---|---|
| 实际脚本与命令 | `code/`（修复后脚本、等价性测试、复算脚本） |
| 环境/哈希 | 本文件 §1；`file_hashes.json` |
| length_report | `length_report/` |
| equivalence_test 与日志 | `equivalence_test/`（李云 CPU 包结论摘要 + 本地测试脚本） |
| audit.md | 本文件 |
| adapter 恢复索引 | `adapter_recovery/` |
