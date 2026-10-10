# Qwen3.8 Sarol 实验记录

日期：2026-10-10  
项目：`citation_integrity_member2`  质量修正版 Sarol 数据  
实验人员：李云

## 1. 实验任务

根据师兄安排，补齐一次新的 Qwen 实验：

1. 接入修复版 Sarol 数据。
2. 在 Dev316 上重新确定提示词、证据输入和运行参数。
3. 在配置确定后运行 Test606。
4. 交付运行配置、原始输出、完整日志、逐条预测、Accuracy、各类指标、Macro-F1 和混淆矩阵。

本记录只记录 Qwen3/Qwen3.8 实验，不包含 MultiVerS 微调实验。

## 2. 数据和代码

### 2.1 修复版数据包

GitHub 仓库：`https://github.com/LeegenSteven/academic-misconduct`  
对应数据目录：`data/quality_v1/sarol/`  
对应脚本目录：`cmj/`

数据包已上传到服务器暂存目录：

```text
/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/
```

解压目录：

```text
/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/extracted/
```

数据包 SHA-256：

```text
27edc84aed1ee74e75c4392f99ea23ae1b53cc82d86318831645bfcbc9baea17
```

数据文件行数核对：

| 文件 | 数量 |
|---|---:|
| `claims-train-model.jsonl` | 2141 |
| `claims-dev-model.jsonl` | 316 |
| `claims-test-model.jsonl` | 606 |
| `corpus.jsonl` | 8515 |

Test 标签统计：

| 标签 | 数量 |
|---|---:|
| `ACCURATE` | 386 |
| `NOT_ACCURATE` | 170 |
| `IRRELEVANT` | 50 |

修复版规则：

- 三分类：`NOT_ACCURATE`、`IRRELEVANT`、`ACCURATE`。
- 原第 1 号槽位由 `NEI` 修正为 `IRRELEVANT`。
- 无检索候选记为 `ABSTAIN`，计入分母但不参与分类。
- `evidence_missing` 样本训练时只计算句子证据损失，标签不变。
- 修正 39 条标签错配：Train 36 条、Test 3 条、Dev 不变。

### 2.2 现有 Qwen3 输入和输出

历史 Dev 输入：

```text
/home/admire/citation_integrity_member2/llm_batch/model_inputs_dev316.jsonl
```

历史 Qwen3 Dev 输出：

```text
/home/admire/citation_integrity_member2/llm_batch/sarol316_qwen3/model_outputs_final.jsonl
/home/admire/citation_integrity_member2/llm_batch/sarol316_qwen3/raw_responses.jsonl
```

历史输入的 claim ID 与修复版 Dev316 完全一致：316/316，无缺失、无多余。

历史输入的候选文档数分布：

| 候选文档数 | 样本数 |
|---:|---:|
| 10 | 23 |
| 15 | 23 |
| 20 | 270 |

因此，当前 Qwen3 输入不是统一 BM25 top-10 配置。

## 3. 历史 Qwen3 结果重评估

使用修复版 Dev 标签对已有 `qwen3:latest` Dev316 输出进行重评估，未产生新的模型推理：

```text
Accuracy = 0.6392405063
Macro-F1 = 0.5545733838
错误数 = 114
优先错误数 = 76
```

重评估输出：

```text
/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/qwen3_dev_reanalysis/
```

该结果只作为历史参考，不作为本次 Qwen3.8 新实验结果。

## 4. Qwen3.8 服务排查过程

### 4.1 首次尝试：现有 qwen3:latest

服务器存在 Ollama 模型 `qwen3:latest`，但使用 OpenAI 兼容接口运行 1 条冒烟测试时超时：

```text
OPENAI_BASE_URL=http://127.0.0.1:11434/v1
OPENAI_MODEL=qwen3:latest
```

检查发现：

- `ollama ps` 显示 `PROCESSOR 100% CPU`。
- 日志显示 `offloaded 0/37 layers to GPU`。
- 该服务实际使用 CPU，不符合 A100 GPU 实验要求。

### 4.2 8080 端口 Qwen3.8 服务

8080 端口存在一个由 root 启动的 `llama-server`，模型为 Qwen3.8。接口可返回结果，但检查发现：

- `nvidia-smi pmon` 没有显示该 `llama-server`。
- GPU 利用率为 0%。
- 使用该服务的批处理单条约需 10～13 分钟。
- 当前账号无法读取 `/root/qwen` 文件，无法直接修改 root 服务。

因此没有继续使用 8080 服务跑正式实验。

### 4.3 使用 sudo 获取用户态运行环境

管理员提示可以使用 `sudo`。确认 `sudo -v` 成功后，检查并复制了以下文件：

```text
/root/qwen/build/bin/llama-server
/root/qwen/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q4_K_P.gguf
/root/qwen/mmproj-Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-BF16.gguf
/root/qwen/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf
```

用户态运行目录：

```text
/home/admire/qwen3_8_runtime/
```

由于 `llama-server` 依赖多个动态库，随后复制了 `/root/qwen/build/bin/` 下的动态库。最终 `ldd` 已确认能够找到：

- `libggml.so.0`
- `libggml-base.so.0`
- `libggml-cpu.so.0`
- `libggml-cuda.so.0`
- `libcudart.so.12`
- `libcublas.so.12`
- `libcuda.so.1`
- `libcublasLt.so.12`

## 5. 正式 GPU 服务

用户态 Qwen3.8 服务运行在：

```text
地址：http://127.0.0.1:8081/v1
模型：Qwen3.8
GPU：GPU1
```

服务启动参数的主要配置：

- `CUDA_VISIBLE_DEVICES=1`
- `--n-gpu-layers all`
- `--split-mode layer`
- `--flash-attn on`
- `--ctx-size 32768`
- `--parallel 1`
- `--temp 1.0`
- `--top-k 20`
- `--top-p 0.95`
- `--jinja`
- 初始版本开启 `--reasoning on --reasoning-effort xhigh`。

GPU 使用证据：

- 用户态 `llama-server` 进程 PID `92042` 曾占用约 18GB 显存。
- `nvidia-smi pmon` 显示 PID `92042` 位于 GPU1。
- 接口 `/v1/models` 返回模型 `Qwen3.8`。

## 6. Dev316 新推理

### 6.1 冒烟测试

使用 GPU1 的 8081 服务完成 1 条冒烟测试：

```text
claim_id=0 status=200 failure=None
```

输出格式正确，标签、证据编号和理由均可解析。

### 6.2 完整 Dev316

正式输出目录：

```text
/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/qwen3_8_dev_gpu1_20261009/
```

核心文件：

- `model_outputs.jsonl`：原始批处理输出。
- `raw_responses.jsonl`：原始接口响应。
- `run.log`：完整运行日志。
- `run_metadata.json`：运行元数据。
- `model_outputs_final.jsonl`：合并并清理后的最终 Dev316 预测。

运行结果：

```text
done = 316
new_ok = 260
new_failed = 56
```

检查后确认：

- 输出行数 316。
- 唯一 claim ID 316。
- 没有缺失 ID 或多余 ID。
- 55 条虽然被脚本标记了非空 `failure_status`，但仍有完整标签、证据和理由；这些状态是模型误填的语义标签，不是接口失败。
- `claim_id=3` 是唯一真正的初始失败：第一次为 `http_exception`，重试时长时间无内容。

### 6.3 claim_id=3 补跑

对 `claim_id=3` 的输入检查：

- `system_prompt` 字符数：355。
- `user_prompt` 字符数：19283。
- 候选证据：90 条。

在深度思考开启时，接口返回：

```text
http_status=200
finish_reason=length
content=""
```

原因是模型将输出额度耗尽在 reasoning 内容中，最终没有返回 JSON。

随后重启用户态 8081 服务，设置：

```text
--reasoning off
```

日志确认：

```text
thinking = 0
model loaded
listening on http://127.0.0.1:8081
```

claim 3 补跑成功，结果为：

```json
{
  "claim_id": 3,
  "label": "NOT_ACCURATE",
  "evidence_ids": ["D01:S05", "D03:S05"],
  "confidence": 0.95,
  "failure_status": "NOT_ACCURATE"
}
```

该条的 `failure_status` 同样是模型误填，合并时已清理为 `null`。

最终文件 `model_outputs_final.jsonl`：

- 316 条完整预测。
- `claim_id=3` 使用关闭 reasoning 后的补跑结果。
- 所有合法预测的 `failure_status` 统一规范为 `null`。
- `model_name` 均为 `Qwen3.8`。

## 7. Dev316 评测结果

评测输出目录：

```text
/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/qwen3_8_dev_gpu1_evaluation_20261010/
```

最终 Dev316 结果：

```text
Accuracy = 0.6930379747
Macro-F1 = 0.6746091856
错误数 = 97
优先错误数 = 31
```

Gold 分布：

```text
ACCURATE = 191
NOT_ACCURATE = 101
IRRELEVANT = 24
```

预测分布：

```text
ACCURATE = 166
NOT_ACCURATE = 132
IRRELEVANT = 18
```

混淆矩阵（行是真实标签，列是预测标签）：

| 真实 \\ 预测 | ACCURATE | NOT_ACCURATE | IRRELEVANT |
|---|---:|---:|---:|
| ACCURATE | 135 | 55 | 1 |
| NOT_ACCURATE | 28 | 70 | 3 |
| IRRELEVANT | 3 | 7 | 14 |

分类指标：

| 标签 | Precision | Recall | F1 |
|---|---:|---:|---:|
| ACCURATE | 0.8133 | 0.7068 | 0.7563 |
| NOT_ACCURATE | 0.5303 | 0.6931 | 0.6009 |
| IRRELEVANT | 0.7778 | 0.5833 | 0.6667 |

主要错误：

- 55 条真实 `ACCURATE` 被预测为 `NOT_ACCURATE`。
- `NOT_ACCURATE` 的 Precision 相对较低（0.5303），说明模型存在较多过度判为不准确的情况。

## 8. 当前限制和注意事项

1. 评测脚本名称和输出中的 `status` 仍沿用了历史重评估表述：`reanalysis_completed_no_new_inference`。这与本次实际新推理不一致，正式汇报时不能直接照抄该字段，应以本记录和运行日志为准。
2. Qwen3.8 Dev 主体推理使用了 reasoning on / xhigh；claim 3 因输出耗尽，使用 reasoning off 补跑。因此本次 Dev 结果存在 1 条运行参数例外，必须在正式记录中说明。
3. 当前 Qwen3 输入的候选证据文档数为 10/15/20，不是统一 BM25 top-10。README 中的 BM25 top-10 规则属于 MultiVerS 脚本，不能直接套到 Qwen3。
4. 目前还没有确认 Test606 的 Qwen3 输入文件或输入生成脚本，因此暂不启动 Test606。
5. 8081 用户态服务依赖当前服务器进程；如果服务器重启或该进程被停止，需要重新启动后再运行实验。

## 9. 当前状态

已完成：

- 修复版 Sarol 数据上传、解压和数量核对。
- 历史 qwen3 Dev316 结果按修复标签重评估。
- Qwen3.8 用户态 CUDA/GPU 服务部署到 GPU1。
- Qwen3.8 Dev316 新推理。
- claim 3 补跑和结果合并。
- Dev316 指标、分类指标和混淆矩阵计算。

待完成：

1. 检查服务器是否已有 Test606 输入或生成脚本。
2. 确认 Test 输入是否沿用 Dev 的候选证据策略和提示词。
3. 固定 Test 运行配置，记录是否开启 reasoning、超时、端口、GPU 和模型文件。
4. 运行 Test606 并保存 606 条逐条预测、原始响应、完整日志和指标。
5. 汇总最终实验报告。

## 10. 下一步检查命令

在服务器上检查现有 Test 输入或生成脚本：

```bash
find ~/citation_integrity_member2 -type f | grep -Ei 'model_inputs|test606|input.*test|sarol.*test'
```

