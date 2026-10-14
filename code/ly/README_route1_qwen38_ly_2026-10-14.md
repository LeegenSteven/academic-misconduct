# Route1 李云：SciCiteVal Adapter 与 PDF 定位准备（2026-10-14）

## 已准备

- `results/route1_qwen38_v1/2026-10-13/sciciteval_train_m0_inputs_2026-10-14.jsonl`
  - 直接从冻结的 `experiment_dataset.tsv` 按 group split 生成 Train 713。
  - 与 Dev M0 使用同一 prompt/evidence 契约：每条 `Cited_content` 只对应 `D01:S01`。
  - 不含 `project_label`，训练标签只从冻结 split CSV 读取，避免把 gold 写入 prompt。
- `results/route1_qwen38_v1/2026-10-13/sciciteval_train_m0_manifest_2026-10-14.json`
  - 记录源 TSV、split 表、Dev prompt reference 和 Train 输入哈希。
- `code/ly/build_sciciteval_train_m0_inputs_v1.py`
  - 复现 Train713 生成过程，避免使用旧版 1034 输入格式。
- `code/ly/route1_qwen38_train_sciciteval_v1.py`
  - 官方 Hugging Face Transformers 底座的 4-bit QLoRA 训练脚本。
  - 与当前路线配置一致：LoRA r16/alpha32/dropout 0.05、学习率 1e-4、micro-batch 1、gradient accumulation 16、max length 4096、seed 42、reasoning off 由服务/提示配置保证。
  - 明确拒绝 `.gguf`，因此当前 A100 上的 GGUF 只能作为 M0 预跑，不能用于正式 adapter。
- `code/ly/route1_qwen38_pdf_positioning_v1.py`
  - PyMuPDF 解析 PDF，保留 PDF SHA-256、1-based 页码、段落/句号、字符偏移和 block bbox；支持 BM25 top-k 定位。

## A100 上的顺序

先确认陈明进锁定的官方 HF 底座目录（目录内应有 `config.json`，不能是 GGUF）：

```bash
cd ~/academic-misconduct-route1
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

## 当前独立验证记录

PDF 定位模块已在两篇本地论文上完成 smoke；PDF 本身未上传 GitHub。

- PointRend：499 句；source SHA-256 `dc544aba7f76d1c395154d638c52e6196095eb9468700828b3b35d1fa250244c`；index SHA-256 `da61f55a91b2eab198e7c4e50448ba2621319bb0ff6178516037701931f9aef2`。
- DySample：456 句；source SHA-256 `8e0939f9c28fcf1832400e302fbaf16237725593cb3c32e36e222e7317cdf50c`；index SHA-256 `b821f3a43d80ab9efc7c7db69806b233cba536c6862f4871bdcd71f4c5da5926`。
- 当前定位粒度标记为 `block_bbox`，表示句子所在文本块的 bbox。

Sarol Test606 属于陈明进的 Sarol 流程；本目录不生成或运行该 Test。
