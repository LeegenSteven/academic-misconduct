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

## 2026-10-25：Mscv可访问归档与最终分类交付

本次补齐原件与可访问索引，沿用已经通过独立审计的六组Test。以上原始分类结果、run01失败记录及run02预算修订说明继续有效。未追加训练、推理或Test选点。

### Mscv训练归档

Mscv于10月16日从同一官方HF底座独立训练SciCiteVal Train713，45步、1 epoch，耗时49.31分钟；训练loss为0.1862243064575725。训练max_length=4096，与正式Test的5120预算分别登记。

| 材料 | 可直接查看的文件 | SHA-256 |
|---|---|---|
| 训练入口 | [route1_qwen38_train_sciciteval_v1.py](../../../../code/ly/route1_qwen38_train_sciciteval_v1.py) | `606f70300d8039d6dd84e9cfa565b39616b3368df5d2e4c13058ad783e8ac0fa` |
| 共享输入/监督mask代码 | [data_contract.py](../../../../code/shared/route1_qwen38/data_contract.py) | `93e881ea4a9d8dc92c897a87862a185bd5527ee58f31567472e29a8ef7261776` |
| 原始训练配置 | [training_config.json](../mscv_training_archive/training_config.json) | `011bdfc438071198b513eae738890549b8c7f98b044b4cf592a256289f838a54` |
| adapter配置 | [adapter_config.json](../mscv_training_archive/adapter_config.json) | `bbc4d950e74884df8b07f82b2ecf588f936b9a7a46284724f22130b1773637a1` |
| 原始完整训练日志 | [train.original.run.log](../mscv_training_archive/train.original.run.log) | `81bd45923a84de3954ed80c0b58e87a9614ab2928e10878ba05edd1c53d4d863` |

归档清单：[manifest.json](../mscv_training_archive/manifest.json)。清单同时登记Train输入/gold、底座revision与配置哈希、全部6个adapter目录文件，以及原件复制来源。训练代码以10月18日冻结快照和原日志命令绑定，当前字节哈希相同。

Mscv权重保留于李云本机 `_A100_Mscv归档_20261019/final_adapter/adapter_model.safetensors`，本次实测SHA-256为 `5d9be2027cf3de78f4df6a89564dab9b3cf970c0d7b9917a4f965b8e88e8bf54`。A100原路径为 `/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/route1_qwen38_v2_train_20261016_gpu3/train/Mscv/final_adapter`。本机原件可用，A100需现有账号权限；本次没有测试远端在线状态，也未建立公开权重下载地址。权重不放入普通Git仓库，跨机器取用后应按清单核对。

### 六组最终文件入口

最终清单：[classification_delivery_manifest.json](classification_delivery_manifest.json)。合计2589次模型输出，对应863条不同Test样本；六组原始预测、指标和完整运行日志仍使用本目录已有原件。此次对12个结果文件、冻结输入/gold及运行日志核对哈希，均匹配此前独立审计；复用原审计的逐条ID、标签解析与指标复算结论。

| 数据集 | 模型 | 原始预测 | 原始指标（含各类P/R/F1与混淆矩阵） |
|---|---|---|---|
| sciciteval | M0 | [逐条预测](test/sciciteval/M0/M0_test_predictions.jsonl) | [指标JSON](test/sciciteval/M0/M0_test_metrics.json) |
| sciciteval | Mbio | [逐条预测](test/sciciteval/Mbio/Mbio_test_predictions.jsonl) | [指标JSON](test/sciciteval/Mbio/Mbio_test_metrics.json) |
| sciciteval | Mscv | [逐条预测](test/sciciteval/Mscv/Mscv_test_predictions.jsonl) | [指标JSON](test/sciciteval/Mscv/Mscv_test_metrics.json) |
| sarol | M0 | [逐条预测](test/sarol/M0/M0_test_predictions.jsonl) | [指标JSON](test/sarol/M0/M0_test_metrics.json) |
| sarol | Mbio | [逐条预测](test/sarol/Mbio/Mbio_test_predictions.jsonl) | [指标JSON](test/sarol/Mbio/Mbio_test_metrics.json) |
| sarol | Mscv | [逐条预测](test/sarol/Mscv/Mscv_test_predictions.jsonl) | [指标JSON](test/sarol/Mscv/Mscv_test_metrics.json) |

以下分项从原始metrics直接整理；行是真实标签，列是预测标签。INVALID单列展示，避免Sarol/M0三分类矩阵合计605被误写为606。准确率和召回率分母仍包含该无效输出。

#### sciciteval / M0

正确 213/257；Accuracy 0.828794；Macro-F1 0.830290；无效 0。

| 类别 | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| ACCURATE | 0.688525 | 0.943820 | 0.796209 | 89 |
| NOT_ACCURATE | 0.896552 | 0.584270 | 0.707483 | 89 |
| IRRELEVANT | 1.000000 | 0.974684 | 0.987179 | 79 |

| Gold / Pred | ACCURATE | NOT_ACCURATE | IRRELEVANT | INVALID |
|---|---:|---:|---:|---:|
| ACCURATE | 84 | 5 | 0 | 0 |
| NOT_ACCURATE | 37 | 52 | 0 | 0 |
| IRRELEVANT | 1 | 1 | 77 | 0 |

#### sciciteval / Mbio

正确 196/257；Accuracy 0.762646；Macro-F1 0.745416；无效 0。

| 类别 | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| ACCURATE | 0.594595 | 0.988764 | 0.742616 | 89 |
| NOT_ACCURATE | 0.967742 | 0.337079 | 0.500000 | 89 |
| IRRELEVANT | 1.000000 | 0.987342 | 0.993631 | 79 |

| Gold / Pred | ACCURATE | NOT_ACCURATE | IRRELEVANT | INVALID |
|---|---:|---:|---:|---:|
| ACCURATE | 88 | 1 | 0 | 0 |
| NOT_ACCURATE | 59 | 30 | 0 | 0 |
| IRRELEVANT | 1 | 0 | 78 | 0 |

#### sciciteval / Mscv

正确 223/257；Accuracy 0.867704；Macro-F1 0.872359；无效 0。

| 类别 | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| ACCURATE | 0.772277 | 0.876404 | 0.821053 | 89 |
| NOT_ACCURATE | 0.858974 | 0.752809 | 0.802395 | 89 |
| IRRELEVANT | 1.000000 | 0.987342 | 0.993631 | 79 |

| Gold / Pred | ACCURATE | NOT_ACCURATE | IRRELEVANT | INVALID |
|---|---:|---:|---:|---:|
| ACCURATE | 78 | 11 | 0 | 0 |
| NOT_ACCURATE | 22 | 67 | 0 | 0 |
| IRRELEVANT | 1 | 0 | 78 | 0 |

#### sarol / M0

正确 299/606；Accuracy 0.493399；Macro-F1 0.510430；无效 1。

| 类别 | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| ACCURATE | 0.850932 | 0.354922 | 0.500914 | 386 |
| NOT_ACCURATE | 0.341969 | 0.776471 | 0.474820 | 170 |
| IRRELEVANT | 0.517241 | 0.600000 | 0.555556 | 50 |

| Gold / Pred | ACCURATE | NOT_ACCURATE | IRRELEVANT | INVALID |
|---|---:|---:|---:|---:|
| ACCURATE | 137 | 234 | 14 | 1 |
| NOT_ACCURATE | 24 | 132 | 14 | 0 |
| IRRELEVANT | 0 | 20 | 30 | 0 |

#### sarol / Mbio

正确 434/606；Accuracy 0.716172；Macro-F1 0.645354；无效 0。

| 类别 | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| ACCURATE | 0.809278 | 0.813472 | 0.811370 | 386 |
| NOT_ACCURATE | 0.516129 | 0.564706 | 0.539326 | 170 |
| IRRELEVANT | 0.750000 | 0.480000 | 0.585366 | 50 |

| Gold / Pred | ACCURATE | NOT_ACCURATE | IRRELEVANT | INVALID |
|---|---:|---:|---:|---:|
| ACCURATE | 314 | 67 | 5 | 0 |
| NOT_ACCURATE | 71 | 96 | 3 | 0 |
| IRRELEVANT | 3 | 23 | 24 | 0 |

#### sarol / Mscv

正确 343/606；Accuracy 0.566007；Macro-F1 0.572741；无效 0。

| 类别 | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| ACCURATE | 0.859813 | 0.476684 | 0.613333 | 386 |
| NOT_ACCURATE | 0.377581 | 0.752941 | 0.502947 | 170 |
| IRRELEVANT | 0.584906 | 0.620000 | 0.601942 | 50 |

| Gold / Pred | ACCURATE | NOT_ACCURATE | IRRELEVANT | INVALID |
|---|---:|---:|---:|---:|
| ACCURATE | 184 | 192 | 10 | 0 |
| NOT_ACCURATE | 30 | 128 | 12 | 0 |
| IRRELEVANT | 0 | 19 | 31 | 0 |

这份交付是六组分类结果的归档收口，不替代真实PDF定位、解释语义验收或Mbio等价性结论。10月25日归档材料与索引随本次分类交付提交；adapter权重仍按上述本机/A100路径及SHA-256取用。
