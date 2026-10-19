# 路线一 Qwen3.8 v2 分类实验复现与交接

记录日期：2026-10-19。记录人：李云。本文记录已经完成的分类实验及其文件定位，供核对和必要时复现。SciCiteVal/Mscv 训练由李云负责；Sarol/Mbio 训练由陈明进负责，李云曾协助在 A100 执行部分运行。真实双 PDF 的逐点证据验收另行开展。

## 已完成状态与边界

- v2 静态校验通过：SciCiteVal Train/Dev/Test 为 713/54/257，Sarol 为 2141/316/606；SciCiteVal 的 10 条冲突隔离。数据入口 `code/ly/run_route1_v2.py --stage verify` 应返回 `passed_static_validation_no_model_run`。
- 两个正式 adapter 从同一官方 HF 底座独立训练，关闭 reasoning。Dev 决定 Mscv `final_adapter` 与 Mbio `checkpoint-100`；Test 没有参与选点。
- 六个分类 Test 单元在 2026-10-18 至 19 日的 `refreeze5120_run02` 完整运行，独立审计通过，合计 2589 条模型输出，对应 863 条不同 Test 样本。Sarol M0 的 1 条无效输出原样保留并按错误计分。
- 这些是分类标签结果。Mscv 的两个 Dev 共 370 条原始响应均只有标签；证据编号、理由和置信度以及真实双 PDF 引用流程不能由分类分数证明已通过。

## 固定文件与模型

| 项目 | 固定值或位置 | SHA-256 |
|---|---|---|
| 官方底座 | `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`；A100 本地 `/home/admire/models/Qwen3.8-27B` | `config.json`: `191e0af232104ed8b65258cf3fb2b842e288008baca7633c11b82a1ac7203aab`；18 分片见陈明进权重核验表 |
| Mscv | `/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/route1_qwen38_v2_train_20261016_gpu3/train/Mscv/final_adapter` | `adapter_model.safetensors`: `5d9be2027cf3de78f4df6a89564dab9b3cf970c0d7b9917a4f965b8e88e8bf54` |
| Mbio | `/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/cmj_sarol_mbio_full_memopt_trial_20261017_gpu2/train/checkpoint-100` | `adapter_model.safetensors`: `0f4019af9d0f510408f841797c1038bb19abfee8b6e5f24dc7f222501776bd09` |
| 入口脚本 | `code/ly/run_route1_v2.py` | `e852d09e0845e18a93877afe6f5afb0dd556df134d584af0b1996e284a165be9` |
| 评测脚本 | `code/cmj/route1_qwen38_eval_v1.py` | `c5a5862512911c37bad0e131d8f7342658c78443f8c1df3a5b0e4ea81eaa1d42` |
| SciCiteVal Test 输入 / gold | `results/route1_qwen38_v2/2026-10-15/sciciteval/test.{inputs,gold}.jsonl` | `da705b96dff43c8077de9ed7c261048ba427795848126ad941f4c7cd9ff73301` / `98512eb476fe31da3f36dea716ea3333008234f2af9ac191afd10d48a854eabd` |
| Sarol Test 输入 / gold | `results/route1_qwen38_v2/2026-10-15/sarol/test.{inputs,gold}.jsonl` | `46b441cd7623ca827113ba5a52ae8a08d34cbbc4d5211b133e6af8595fc27391` / `696d6d9290c03e3ca79ff705aeeab52161932f3c2b229db87298427e900caeae` |

Mscv 的完整 `final_adapter` 和原始 Train713 日志另存于李云本地 `发给师兄_本周汇报_2026-10-19/03_模型与Dev核验/Mscv训练与adapter/`。日志记录 45/45 步、49.31 分钟，SHA-256 为 `81bd45923a84de3954ed80c0b58e87a9614ab2928e10878ba05edd1c53d4d863`。该交接包不含 27B 底座；运行时仍须使用已经核验的官方权重。

## 配置修订与实际运行

初次 Test 的 4096 总 token 上限在 Sarol `claim_id=19` 中止：4238 个输入 token 加 512 个生成预算，合计 4750。程序没有静默截断。经李云转达陈明进确认，六个 Test 单元统一采用 `--max-length 5120 --max-new-tokens 512`，使用全新 `run02` 输出目录完整重跑，不拼接 run01 结果。该变更发生于 Test 开始后，需与结果一起披露；它仅改变推理前长度检查阈值，未改模型、输入、checkpoint、解码或解析代码。较严格 4096 检查下已完成的 Dev 预测保留。

推理使用 NF4 量化、BF16 计算、base tokenizer、`enable_thinking=False`、greedy、首次响应不重试。实际环境记录为 torch `2.11.0+cu130`、transformers `5.8.0`、peft `0.21.2`、bitsandbytes `0.50.2`、accelerate `1.14.0`。上述版本和权重须与日志、训练配置及底座核验记录同时核对。

原始输出保存在 `results/route1_qwen38_v2/2026-10-19/test_refreeze5120_run02/`。A100 原目录为 `/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/route1_qwen38_v2_test_20261018_refreeze5120_run02`。六组运行日志 `run02.run.log` 的 SHA-256 为 `0f32732e31b9fbad62370f8e2c72a7bd8abd3b0cdb24a968c34c59b36f78073b`；`20_六个Test独立复核_20261019.json` 核对了 12 个结果文件、2589 行预测和六次完成记录。

以下命令只展示复现入口。**不要指向已经存在的 `run02` 目录**；只有确需重新推理时，先核验文件哈希并指定全新的输出目录。在 A100 仓库根目录运行：

```bash
python code/ly/run_route1_v2.py --stage verify
python code/ly/run_route1_v2.py --stage test --dataset both --models M0 Mbio Mscv --model-path /home/admire/models/Qwen3.8-27B --output-root /home/admire/新建的空输出目录 --mbio-adapter /home/admire/citation_integrity_member2/incoming/quality_v1_20261009/cmj_sarol_mbio_full_memopt_trial_20261017_gpu2/train/checkpoint-100 --mscv-adapter /home/admire/citation_integrity_member2/incoming/quality_v1_20261009/route1_qwen38_v2_train_20261016_gpu3/train/Mscv/final_adapter --max-length 5120 --max-new-tokens 512 --dry-run
```

核对 dry-run 打印的六条命令、GPU 可用性和新目录后，若确需复现，去掉 `--dry-run` 并保留完整日志。分类评测调用只传冻结的 `system_prompt` 与 `user_prompt`；gold 保持旁路，不进入模型提示词。原 run02 可直接审计，无须为生成汇报而重复推理。

## 分类结果与待完成验收

| 数据集 | M0 Test | Mbio Test | Mscv Test |
|---|---|---|---|
| SciCiteVal 257 条 | 213/257；Macro-F1 0.8303 | 196/257；0.7454 | 223/257；0.8724 |
| Sarol 606 条 | 299/606；0.5104 | 434/606；0.6454 | 343/606；0.5727 |

20 条 Test 代表案例已生成两份盲复核表，仍待李云与陈明进分别独立填写并裁决。施引 PDF 现有原共同清单 5 对/10 点及另列候选 2 对/11 点，均仅完成准备；新增候选是否纳入正式范围待确认，独立验收通过数为 0。陈明进侧被引 PDF 全文证据与施引点的逐点对齐、真实双 PDF 引用判定及接受率仍未完成。跨人员重载的技术结果已复核，陈明进接受由李云转达；原始 `human_signoff_complete=false` 文件保留，单独本人签核件仍待补齐。
