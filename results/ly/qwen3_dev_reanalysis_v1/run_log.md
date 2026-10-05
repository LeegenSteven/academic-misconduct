# 本地运行记录

日期：2026-10-05

## 执行内容

本次只做已有 Qwen3 Dev316 输出的离线重评，没有调用模型，没有连接或修改 A100。

## 使用文件

```text
predictions: source_model_outputs_qwen3_dev316.jsonl
gold:       data/quality_v1/sarol/gold_mapping-dev.csv
claims:     data/quality_v1/sarol/claims-dev-model.jsonl
inputs:     source_model_inputs_dev316.jsonl
```

## 核验结果

- predictions、claims、model_inputs、gold 均为 316 条。
- 四组文件的 `claim_id` 集合完全一致。
- 预测标签均为 `ACCURATE`、`NOT_ACCURATE` 或 `IRRELEVANT`。
- 旧输出中的 `evidence_ids` 均能在对应历史输入的允许证据编号中找到。
- Accuracy：0.639241。
- Macro-F1：0.554573。
- NOT_ACCURATE → ACCURATE/IRRELEVANT：76 条。

## 下一步门槛

陈明进师兄需要在 A100 上用 `config_draft.json` 先跑新的 Dev，回传模型 digest、实际 prompt、证据输入构造、解码参数和完整日志；Dev 配置确认后才能运行 Test606。
