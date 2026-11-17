# Adapter 恢复索引（adapter_recovery_index.md）

- 日期：2026-10-24
- 目标：任何人可从本索引在 A100 上恢复 Sarol Mbio QLoRA adapter 并做推理/继续训练。
- 底座：Qwen/Qwen3.8-27B，revision 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0（HF 官方，非 GGUF）。A100 路径 `/home/admire/models/Qwen3.8-27B`；本地路径 `C:\Users\Administrator\Documents\models\Qwen3.8-27B`。

## 1. A100 存储位置

```
/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/cmj_sarol_mbio_full_memopt_trial_20261017_gpu2/train/
├── checkpoint-100/
│   ├── adapter_model.safetensors   SHA256 0f4019af9d0f510408f841797c1038bb19abfee8b6e5f24dc7f222501776bd09
│   ├── adapter_config.json         SHA256 b425bcd6ba101d02dcb1dd8d9f892b315bd082a7b6feeba938b43bc58aedc2f8
│   └── trainer_state.json / optimizer 等
├── final_adapter/
│   ├── adapter_model.safetensors   目录整体 SHA256 9f03dccc3627c07fc021093f9a2ce6df027444d9ea0421b5d1e21223b75d18e8
│   ├── adapter_config.json         SHA256 b425bcd6ba101d02dcb1dd8d9f892b315bd082a7b6feeba938b43bc58aedc2f8
│   └── tokenizer 文件（tokenizer.json / tokenizer_config.json 等）
├── training_config.json            SHA256 f468c2cc6c7c16098c814a106db8eb0f44f235228a5b5ee5802a0d1518328d42
└── train.log
```

## 2. 冻结候选选择依据

- checkpoint-100（Sarol Dev Macro-F1 **0.599595**）> final（Sarol Dev Macro-F1 0.591875）
- final 在 Sarol 多对 3 但 NA 召回降；checkpoint-100 为固定冻结候选。
- Dev 四组指标：Sarol step100/final、SciCiteVal step100/final（见 10/17 交接包 manifest）。

## 3. 重载与推理（参照 10/17 smoke reload 实测）

10/17 冒烟重载实测：加载底座 + 加载 final_adapter + 32 条推理，620s（10.3min），Accuracy 17/32=0.53125、Macro-F1 0.5706417624521073、0 无效输出。

重载脚本：`code/route1_qwen38_eval_v1.py`（本归档 `code/` 目录不含，位于仓库 `code/cmj/route1_qwen38_eval_v1.py`，A100 侧 10/17 已使用同款）。

命令模式（A100）：
```
python route1_qwen38_eval_v1.py \
  --model-path /home/admire/models/Qwen3.8-27B \
  --adapter <train_dir>/checkpoint-100|final_adapter \
  --inputs <eval_inputs.jsonl> \
  --gold <eval_gold.jsonl> \
  --output <out_dir>
```

注意：A100 环境 transformers 5.8.0 加载 adapter 需与训练时 PEFT 版本一致（0.21.2），重载后核对 `adapter_config.json` 的 `r=16 / alpha=32 / dropout=0.05 / target_modules` 七模块清单。

## 4. 恢复验证标准

1. 加载成功无报错，`model.print_trainable_parameters()` 显示 trainable 79,691,776（0.2954%）；
2. 推理输出与 10/17 reload 指标同量级（无需逐位一致）；
3. 训练日志/配置哈希与 §1 一致。
