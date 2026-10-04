# A100 与 Qwen3 Test 核查记录

日期：2026-10-04

## 本地已核实的材料

- 历史 A100 检查记录显示主机账号为 `admire@s2.admirecn.de:7002`，当时 Ollama 中存在 `qwen3:latest`，模型摘要为 Qwen3 约 8.2B、Q4_K_M，模型 digest 记录为 `500a1f067a9f...`。
- 本地已保存 Qwen3 Sarol Dev 316 条输出：`成员2_本周任务_2026-09-17/03_大模型/runs/sarol316_qwen3/model_outputs_final.jsonl`，记录数 316，字段含 `model_name=qwen3:latest`。
- 本地已保存 Qwen3 SciCiteVal 1034 条输出：`成员2_本周任务_2026-09-17/03_大模型/runs/sciciteval1034_qwen3/model_outputs.jsonl`，记录数 1034，字段含 `model_name=qwen3:latest`。
- 本地现有 606 条 Test 文件 `陈明进，20261003，606test/test_predictions_step2141.jsonl` 记录数为 606，但字段是 `claim_id/gold/pred`，配套 README 和日志明确标为 MultiVerS `step2141` 的 Test 评测，不是 Qwen3 输出。

## A100 连接尝试

- 按历史操作记录对 `s2.admirecn.de:7002` 做了只读 SSH 连接尝试；当前环境在 SSH 握手阶段被远端关闭，未进入服务器。
- 对历史记录中的两个直连 IP 做了只读登录尝试，网络端口可达，但当前环境没有可用的私钥/SSH agent，服务器返回 `Permission denied (publickey,password)`。
- 本机 `C:\Users\y\.ssh` 只有 `known_hosts`，没有可用私钥。因此本次不能确认 A100 当前目录中是否存在 606 条 Qwen3 Test 输出，也没有修改或启动任何远程任务。

## 结论

A100 上曾经有 Qwen3，且已有 Dev/SciCiteVal 输出；但“同一份 606 条 Test 的 Qwen3 原始输出、冻结配置、运行日志、输入哈希和资源登记”仍未在本地或本次远程只读核查中找到。不能把 MultiVerS 的 606 条结果改称 Qwen3，也不能据此声称 Qwen3 Test 已完成。

## 后续需要的材料

请陈明进或具备服务器登录权限的人回传以下任一完整材料：

1. 606 条 Qwen3 Test 原始输出 JSONL、对应输入文件哈希、模型/量化版本、prompt/模板、解码参数和运行日志；或
2. 明确回复服务器上没有这份输出，并登记为按同一冻结配置在 A100 重跑，先记录资源和预计时间，不直接开跑。

如果只拿到输出而没有配置和日志，只能做结果读取，仍不能完成可复现复算。
