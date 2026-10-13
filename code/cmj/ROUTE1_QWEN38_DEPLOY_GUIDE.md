# 路线一 Qwen3.8-27B QLoRA 训练部署指南（A100）

## 一、环境要求

- Python 3.9+
- CUDA 12.1+（A100推荐cu124/cu128）
- GPU显存：≥16GB（4-bit QLoRA训练27B）
- 磁盘空间：≥80GB（模型54GB + adapter + 输出）

## 二、安装依赖

```bash
pip install torch transformers peft bitsandbytes accelerate rank_bm25 pymupdf
```

验证：
```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
python -c "import peft, bitsandbytes, accelerate; print('peft', peft.__version__, 'bnb', bitsandbytes.__version__)"
```

## 三、需要准备的文件

### 1. 模型权重
- 官方 Qwen/Qwen3.8-27B（约54GB）
- 下载方式：
  ```bash
  # 方式1：huggingface-cli
  huggingface-cli download Qwen/Qwen3.8-27B --local-dir /path/to/Qwen3.8-27B
  
  # 方式2：Python
  python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3.8-27B', local_dir='/path/to/Qwen3.8-27B')"
  ```

### 2. 数据文件（GitHub已有，git pull即可）
- Sarol BM25 top-10输入：`results/route1_qwen38_v1/2026-10-13/sarol_bm25_top10_inputs_v1_2026-10-13/`
  - model_inputs_train_bm25_top10_sentences.jsonl (2141条)
  - model_inputs_dev_bm25_top10_sentences.jsonl (316条)
  - model_inputs_test_bm25_top10_sentences.jsonl (606条)
- Sarol gold标签：`data/quality_v1/sarol/gold_mapping-{train,dev,test}.csv`
- SciCiteVal数据：李云自己准备

### 3. 脚本（GitHub已有）
- 训练：`code/cmj/route1_qwen38_train_sarol_v1.py`
- 评测：`code/cmj/route1_qwen38_eval_v1.py`
- 检索：`code/cmj/route1_qwen38_fulltext_retriever_v1.py`

## 四、修改路径配置

训练脚本和评测脚本中的路径是本地硬编码，需要修改：

**训练脚本 `route1_qwen38_train_sarol_v1.py` 顶部：**
```python
MODEL_PATH = "/path/to/Qwen3.8-27B"          # 改成A100上的模型路径
SAROL_INPUT_DIR = "/path/to/sarol_bm25_top10_inputs_v1_2026-10-13"  # 改成输入路径
SAROL_GOLD_DIR = "/path/to/quality_v1/sarol"  # 改成gold路径
OUTPUT_DIR = "/path/to/output/mbio_sarol_adapter_v1"  # 改成输出路径
```

**评测脚本 `route1_qwen38_eval_v1.py` 顶部：**
```python
MODEL_PATH = "/path/to/Qwen3.8-27B"
SAROL_INPUT_DIR = "/path/to/sarol_bm25_top10_inputs_v1_2026-10-13"
SAROL_GOLD_DIR = "/path/to/quality_v1/sarol"
OUTPUT_DIR = "/path/to/output"
```

或者用命令行参数 `--output_dir` 指定输出目录。

## 五、运行命令

### 1. 冒烟测试（32条，验证流程）
```bash
python code/cmj/route1_qwen38_train_sarol_v1.py --smoke
```
预期：32条训练完成，adapter保存成功，无OOM。

### 2. 正式训练（1 epoch）
```bash
python code/cmj/route1_qwen38_train_sarol_v1.py --epochs 1
```
A100预计：1-2小时。输出包括：
- `final_adapter/` — 最终adapter权重
- `checkpoint-*/` — 中间checkpoint
- `training_config.json` — 训练配置
- 训练日志

### 3. Dev评测（M0底座基线）
```bash
python code/cmj/route1_qwen38_eval_v1.py --split dev --model_name M0
```

### 4. Dev评测（Mbio adapter）
```bash
python code/cmj/route1_qwen38_eval_v1.py --split dev --adapter /path/to/final_adapter --model_name Mbio
```

### 5. Test评测（M0和Mbio）
```bash
python code/cmj/route1_qwen38_eval_v1.py --split test --model_name M0
python code/cmj/route1_qwen38_eval_v1.py --split test --adapter /path/to/final_adapter --model_name Mbio
```

## 六、训练配置（已写死在脚本中）

| 参数 | 值 |
|---|---|
| 量化 | 4-bit NF4 |
| LoRA rank | 16 |
| LoRA alpha | 32 |
| LoRA dropout | 0.05 |
| 学习率 | 1e-4 |
| micro-batch | 1 |
| 梯度累积 | 16 |
| 最大长度 | 4096 tokens |
| 随机种子 | 42 |
| 监督目标 | 只监督 `{"label":"ACCURATE"}` |
| target_modules | q/k/v/o/gate/up/down_proj |

A100上可以把micro-batch调到4-8，加快训练。

## 七、输出文件说明

训练输出：
- `final_adapter/` — adapter权重（可直接用PeftModel加载）
- `training_config.json` — 完整训练配置（模型路径、超参、样本数、耗时）

评测输出：
- `{model}_{split}_predictions.jsonl` — 逐条预测（claim_id, gold, pred, raw_output）
- `{model}_{split}_metrics.json` — 指标（accuracy, macro_f1, 三类P/R/F1, 混淆矩阵）

## 八、常见问题

1. **OOM**：降低micro-batch到1，开启gradient_checkpointing（已开启）
2. **bitsandbytes报错**：确认CUDA版本匹配，`pip install bitsandbytes --upgrade`
3. **模型下载慢**：配置代理或用modelscope镜像
4. **输出解析失败**：评测脚本有回退机制，会标记为INVALID并计入错误
5. **adapter加载失败**：确认adapter路径下有adapter_config.json和adapter_model.safetensors

## 九、目录结构建议

```
/workspace/
├── models/
│   └── Qwen3.8-27B/           # 底座模型
├── data/
│   ├── sarol_bm25_top10/      # Sarol输入
│   └── quality_v1/sarol/      # Sarol gold
├── code/
│   └── cmj/                   # 训练/评测/检索脚本
└── output/
    ├── mbio_sarol_adapter/    # 训练输出
    └── eval_results/          # 评测输出
```
