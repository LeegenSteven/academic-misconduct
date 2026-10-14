# Route1 李云：SciCiteVal Adapter 与 PDF 定位准备（2026-10-14）

## 已准备

- `results/route1_qwen38_v1/2026-10-13/sciciteval_train_m0_inputs_2026-10-14.jsonl`
  - 从冻结的 1034 条输入按 group split 过滤出 Train 713。
  - 不含 `project_label`，训练标签只从冻结 split CSV 读取，避免把 gold 写入 prompt。
- `results/route1_qwen38_v1/2026-10-13/sciciteval_train_m0_manifest_2026-10-14.json`
  - 记录输入、split 表哈希、数量和标签分布。
- `code/ly/route1_qwen38_train_sciciteval_v1.py`
  - 官方 Hugging Face Transformers 底座的 4-bit QLoRA 训练脚本。
  - 与当前路线配置一致：LoRA r16/alpha32/dropout 0.05、学习率 1e-4、micro-batch 1、gradient accumulation 16、max length 4096、seed 42、reasoning off 由服务/提示配置保证。
  - 明确拒绝 `.gguf`，因此当前 A100 上的 GGUF 只能作为 M0 预跑，不能用于正式 adapter。
- `code/ly/route1_qwen38_pdf_positioning_v1.py`
  - PyMuPDF 解析 PDF，保留 PDF SHA-256、1-based 页码、段落/句号、字符偏移和 block bbox；支持 BM25 top-k 定位。

## A100 上的顺序

先确认陈明进锁定的官方 HF 底座目录（目录内应有 `config.json`，不能是 GGUF）：

```bash
cd ~/citation_integrity_member2
python code/ly/route1_qwen38_train_sciciteval_v1.py --help
```

收到官方底座路径后，先做 32 条 smoke：

```bash
python code/ly/route1_qwen38_train_sciciteval_v1.py   --model-path /path/to/official/Qwen3.8-27B   --inputs results/route1_qwen38_v1/2026-10-13/sciciteval_train_m0_inputs_2026-10-14.jsonl   --split-csv results/route1_qwen38_v1/2026-10-13/sciciteval_group_split_provisional_2026-10-13.csv   --output-dir incoming/quality_v1_20261009/qwen3_8_sciciteval_adapter_smoke_20261014   --smoke
```

Smoke 通过并核对底座版本后，再运行正式 Train713：

```bash
python code/ly/route1_qwen38_train_sciciteval_v1.py   --model-path /path/to/official/Qwen3.8-27B   --inputs results/route1_qwen38_v1/2026-10-13/sciciteval_train_m0_inputs_2026-10-14.jsonl   --split-csv results/route1_qwen38_v1/2026-10-13/sciciteval_group_split_provisional_2026-10-13.csv   --output-dir incoming/quality_v1_20261009/qwen3_8_sciciteval_adapter_v1_20261014
```

PDF 定位先建立索引，再对 claim 查询：

```bash
python code/ly/route1_qwen38_pdf_positioning_v1.py   --pdf /path/to/paper.pdf   --save-index incoming/quality_v1_20261009/pdf_index/paper.jsonl

python code/ly/route1_qwen38_pdf_positioning_v1.py   --index incoming/quality_v1_20261009/pdf_index/paper.jsonl   --query 'claim text' --top-k 10
```

正式 adapter 输出必须记录官方底座路径/版本、输入哈希、split CSV 哈希、脚本版本和训练配置；当前 GGUF M0 结果继续标记为 `completed_prerun_gguf`。
