# Sarol Train2141 长度复算报告（length_report）

- 日期：2026-10-24
- 口径：官方 Qwen3.8-27B tokenizer + `shared.route1_qwen38.data_contract.encode_assistant_record`（apply_chat_template、字符偏移 mask、EOS 监督、5120 超长显式报错）逐条编码复算。**非文本拼接估算**。
- 数据：`results/route1_qwen38_v2/2026-10-15/sarol/train.inputs.jsonl` + `train.gold.jsonl`

## 结果（all_pass=true）

| 指标 | 值 |
|---|---|
| 样本数 | 2141 |
| 长度 min / max | 508 / 4924 |
| 长度 mean / median | 824.39 / 787 |
| 超 4096 条数 | 3（见下） |
| 5120 下超长条数 | 0（未截断、未漏样本） |
| 监督 token 合计 | 20042 |
| EOS 被监督样本 | 2141/2141 |
| 编码失败 | 0 |

标签分布：ACCURATE 1368 / NOT_ACCURATE 630 / IRRELEVANT 143

超 4096 三条：

| claim_id | 长度 | 标签 |
|---|---|---|
| 237 | 4789 | ACCURATE |
| 250 | 4924 | NOT_ACCURATE |
| 256 | 4866 | NOT_ACCURATE |

## 与 10/17 交接记录的一致性

3 条超 4096、最大 4924、5120 未截断、监督 token 20042 —— 与 10/17 交接记录完全吻合。

## 口径注意

本报告（官方 tokenizer 真实编码）与 `deliverables/2026-10-19_显存优化方案补齐/sarol_train_length_report_v2.json`（文本拼接估算口径、max 9475）不同；旧文件为历史估算材料，正式口径以本报告为准。

## 文件

- 复算脚本：`code/recount_train2141_lengths_20261024.py`
- 结果 JSON：`length_report/sarol_train2141_length_recount_20261024.json`
