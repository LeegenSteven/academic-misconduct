# Qwen3 Dev316 旧输出重评与新实验准备

日期：2026-10-05

本目录完成了两项本地工作：

1. 用修复版 `sarol-quality-v1` 的 Dev gold 对已有 Qwen3 Dev316 输出重新计分；
2. 准备新的 Dev/Test 实验所需的输入哈希、提示词、输出 schema 和配置草案。

本目录**没有启动模型推理**。重评结果不能写成新的 A100 实验结果；新的 Dev 运行仍需在 A100 上按 `config_draft.json` 确认配置后执行。

## 旧 Dev 输出重评

- 样本数：316
- gold：ACCURATE 191、NOT_ACCURATE 101、IRRELEVANT 24
- Accuracy：0.639241
- Macro-F1：0.554573
- NOT_ACCURATE 被判为 ACCURATE 或 IRRELEVANT：76 条
- 旧输出、旧输入、运行元数据和哈希均保留在本目录。

详细结果见 `metrics_reanalysis.json`、`error_cases.csv` 和 `manifest.json`。

## 重要限制

- 旧输出只用于按新 gold 复评，不能替代新 Dev 运行。
- Test606 只能在 Dev 配置冻结后运行。
- `confidence` 只是模型自报置信度；校准完成前 `score_support`、`score_distort`、`score_unrelated` 均保持 `null`。
- 模型 digest、A100 环境和完整新运行日志需要由实际执行者补齐。
