# Mbio纠正训练与评估归档（2026-11-01）

本页交付纠正Mbio的实际A100训练、Sarol Dev选点、两个Test及本机原件核验结果。原Mbio、M0、Mscv及原六组Test保留，新Mbio另列。技术归档核验完成，正式共同验收尚未登记。

## 实施与选点

- 李云在A100执行。训练2141条、有效监督token合计20042，134步、1轮，约221.8分钟。执行日志见[train.log](corrected_20261031/run/train.log)，配置见[training_config.json](corrected_20261031/train/training_config.json)。
- 冻结训练脚本SHA256：`9a47a2daa2c92b19d6274e26b526075a5402406e3de068852585ff32818e4aba`；[实际源码快照](corrected_20261031/source/code/cmj/route1_qwen38_train_sarol_memopt_v1.py)。目标为每个累积窗口有效监督token的交叉熵sum/N，外层不额外除以GA步数。154/126是既有29条CPU对照的两个窗口计数，不是全Train固定分母。训练配置文件原loss_implementation描述按字节保留，精确实现以冻结脚本为准。
- QLoRA r/alpha/dropout=16/32/0.05，LR=1e-4，microbatch=1，累积16，seed=42，训练上限5120。分类为NF4+BF16、greedy、5120/512、enable_thinking=false、无重试；未按88倍估计缩放学习率。
- Sarol Dev Macro-F1为唯一选点规则。checkpoint-100为0.5665071770，checkpoint-134为0.5969663577，因此选中checkpoint-134；两套Test均使用该checkpoint。[选点日志](corrected_20261031/run/dev_selection.run.log)、[两候选原始Dev文件](corrected_20261031/dev_selection/)。

## 新旧Test结果

| 数据集 | 旧Mbio checkpoint-100正确数 | 纠正Mbio checkpoint-134正确数 | 旧Accuracy | 纠正Accuracy | 旧Macro-F1 | 纠正Macro-F1 | Macro-F1变化（0–1） |
|---|---|---|---|---|---|---|---|
| Sarol | 434/606 | 439/606 | 0.716172 | 0.724422 | 0.645354 | 0.648716 | +0.003362 |
| SciCiteVal | 196/257 | 192/257 | 0.762646 | 0.747082 | 0.745416 | 0.724066 | −0.021350 |

新旧输入/gold身份一致，预算同为5120/512。相对旧Mbio，Sarol修复32条、新增错误27条，净增正确5条；SciCiteVal修复0条、新增错误4条。该逐条比较的参照是旧Mbio，不是M0，也不改原45条分析或冻结gold。纠正训练的结果在两个域上方向不同，不宣称普遍增益。

- 新Test：[Sarol预测](corrected_20261031/test/sarol/Mbio_corrected_ckpt134/Mbio_corrected_ckpt134_test_predictions.jsonl)、[Sarol指标](corrected_20261031/test/sarol/Mbio_corrected_ckpt134/Mbio_corrected_ckpt134_test_metrics.json)、[SciCiteVal预测](corrected_20261031/test/sciciteval/Mbio_corrected_ckpt134/Mbio_corrected_ckpt134_test_predictions.jsonl)、[SciCiteVal指标](corrected_20261031/test/sciciteval/Mbio_corrected_ckpt134/Mbio_corrected_ckpt134_test_metrics.json)、[完整Test日志](corrected_20261031/run/test.run.log)。
- 旧Test：[原六组结果](../../../route1_qwen38_v2/2026-10-19/test_refreeze5120_run02/README.md)。

## 原件核验与权重身份

本机核验：整包SHA256与用户通过SSH读取的A100校验值一致，包内25项载荷大小/哈希一致。两组Dev和两组Test均核对冻结ID、顺序、gold、原始响应解析、全部评分字段，结果一致；四组无效输出和触及生成上限数均为0。[完整核验收据](a100_archive_validation_20261101.json)、[逐文件清单](corrected_20261031/manifest.json)。

| 原件 | SHA256 |
|---|---|
| 整包 `mbio_corrected_ckpt134_handoff_20261101.tar.gz`（299580520字节） | `75928854a840efd11d59a21bedc2706f7d9a489f27ee838f21d6b303d1f295cb` |
| checkpoint-134 adapter_model.safetensors | `cabbde8d1027a2c7dcd61e7404c5028b7108ce6879252357f3e52b8281407f25` |
| checkpoint-134 adapter_config.json | `d5951f1c125680cc73a0031b5c20ffbfe7ce050eb2cf81fd1fd327adf5e68944` |
| training_config.json | `24d8251ae7a896079c69962b3b7b335fb7856fc743a8353f6fdb876068de9584` |

A100原包：`/home/admire/mbio_corrected_ckpt134_handoff_20261101.tar.gz`；选中权重：`/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/cmj_sarol_mbio_corrected_20261031/train/checkpoint-134`。本机原包路径及选中权重实算哈希见核验收据。Git保存日志、预测、指标、配置和源码快照；权重、完整tokenizer.json、training_args.bin经原包取回，清单中明确标为未随Git发布。原包不含27B底座或优化器状态。

训练、Dev/Test完成由原日志及产物核验；独立进程退出码文件未随包回收，不补造退出码。清单记录的软件包版本是在归档时读取的环境，不能替代执行时日志。既有CPU FP32与旧27B/BF16等价性结论保持原范围，不由本次归档扩展为27B逐位等价。

## 决策依据与下一步

[陈明进冻结确认](发给李云_Mbio纠正训练冻结配置确认_20261031.md)、[负责人统一口径（用户转述）](路线一负责人三项统一口径_用户转述_20261030.txt)、[分母核查方案](给金城_Mbio归一化分母核查与纠正方案_20261030.md)、[接收核对及证据边界](陈明进10月30日方案_接收核对与执行缺口.md)。这些来文保留当时状态，不回写为事后共同签核。

下一步将本页和已核原件交接陈明进及负责人，按实际回复登记共同意见。现有选点和Test已完成，无需为发布重跑。PDF固定20点及杨独立复演按其独立任务状态推进，不因Mbio归档完成而改写为PDF整体验收通过。
