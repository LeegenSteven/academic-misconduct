# 路线一 v2 正式 Test：5120 配置重跑（run02）

这份交付保留 2026-10-18 在 A100 上依次运行的六个 Test 单元的原始逐条预测、指标和完整运行日志；2026-10-19 从服务器复制并独立复核。`test/` 内六对原始文件与 A100 输出字节一致，未合并、补跑或改写预测。

## 配置与范围

- 官方底座：`Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`。
- 模型：M0 官方底座；Mbio `checkpoint-100`（adapter 权重 SHA-256 `0f4019af9d0f510408f841797c1038bb19abfee8b6e5f24dc7f222501776bd09`）；Mscv `final_adapter`（`5d9be2027cf3de78f4df6a89564dab9b3cf970c0d7b9917a4f965b8e88e8bf54`）。
- 三个模型在 SciCiteVal Test257 与 Sarol Test606 上评测，共六个单元。统一 `max_length=5120`、`max_new_tokens=512`、`enable_thinking=False`、greedy 解码、无重试；超过输入加生成预算时直接失败，不截断。
- `max_length` 从 4096 修订为 5120，是因为 run01 在 Sarol Test `claim_id=19` 遇到 `4238+512>4096` 而中止。陈明进同意统一修订的记录来源为李云在当前对话中的转达；独立签字文件未附。参见 `test_config_freeze.json`。run01 与本次结果不混用。

## 分类结果

| 数据集 | 模型 | 正确/总数 | Accuracy | Macro-F1 | 无效输出 |
| --- | --- | ---: | ---: | ---: | ---: |
| SciCiteVal | M0 | 213/257 | 0.828794 | 0.830290 | 0 |
| SciCiteVal | Mbio | 196/257 | 0.762646 | 0.745416 | 0 |
| SciCiteVal | Mscv | 223/257 | 0.867704 | 0.872359 | 0 |
| Sarol | M0 | 299/606 | 0.493399 | 0.510430 | 1 |
| Sarol | Mbio | 434/606 | 0.716172 | 0.645354 | 0 |
| Sarol | Mscv | 343/606 | 0.566007 | 0.572741 | 0 |

这些是分类指标；adapter 的标签输出不代表四字段解释结构合格。Sarol/M0 的一条无效输出保留在原始文件中，作为错误计入分母和对应 gold 类的 false negative。Test 指标仅作最终报告，不用于重新选择 checkpoint。

## 核验与来源

`independent_audit.json` 记录了逐条 ID/gold 顺序、冻结输入和 gold 哈希、原始预测哈希、raw response 解析、单次推理与 token 预算，以及 Accuracy、Macro-F1、混淆矩阵和各类指标的独立复算。六个单元均通过。`run02.run.log` 中六条执行命令、六个完成标记与对应分数也逐项吻合，未发现异常回溯。

- A100 原始输出目录：`/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/route1_qwen38_v2_test_20261018_refreeze5120_run02`
- 完整日志 SHA-256：`0f32732e31b9fbad62370f8e2c72a7bd8abd3b0cdb24a968c34c59b36f78073b`
- 5120 冻结记录 SHA-256：`e086876bb9b74cecd7e7a47f9b80ddc9744d96ddb1af63cc38a93a908e9b5353`
- 审核脚本及未改写的本地审核记录保留在李云本地 `路线一冻结核验_20261018/`。
