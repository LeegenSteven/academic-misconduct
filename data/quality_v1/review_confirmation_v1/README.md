# 复核确认版：两位同学取用说明

版本：`review-confirmed-v1-2026-10-04`。

项目负责人接受本轮27条明确建议，6条保留待定。示范数据另外17条沿用原有人工裁决。本版只记录样本编号、有效标签、状态和用途；对应原引文及原人工记录继续通过原样本编号关联。

| 数据 | 全量 | 有可用标签 | 准确 | 不准确 | 无关 | 待定 |
|---|---:|---:|---:|---:|---:|---:|
| 示范数据 | 30 | 28 | 16 | 10 | 2 | 2 |
| PMC唯一候选 | 20 | 16 | 14 | 1 | 1 | 4 |

`label_decisions.jsonl`含全部50条的有效标签。直接读取`gold`；`gold=null`表示待定，应排除于带标签评测。旧标签仅保留在`previous_adjudicated_label`，不能给待定记录兜底。`SUPERVISOR_CONFIRMED`为本轮负责人确认，`EXISTING_HUMAN_ADJUDICATION`为沿用原裁决；这不新增两位同学的独立标注次数。

原PMC-OA-V2-08重复07、18重复17。本版以两个重新提取的引用句PMC-REPAIR-08、PMC-REPAIR-18替换；前者确认为准确，后者待定。新条目的public_source_locator提供施引与被引URL、XML哈希、段落和句子编号、目标参考文献及同段第几次引用，供从公开来源复现提取。请通过新编号关联新引用句，不能把新标签赋给旧重复句。demo_19核对了完整摘要和真实参考文献25的引用链，被引全文仍未获取。

待定编号：demo_17、demo_25、PMC-OA-V2-04、PMC-OA-V2-09、PMC-OA-V2-19、PMC-REPAIR-18。

## 现在重跑的主数据

Sarol训练数据版本仍为`sarol-quality-v1`，位于[../sarol/](../sarol/)。读取claims-train-model.jsonl（2141条）、claims-dev-model.jsonl（316条）、claims-test-model.jsonl（606条）及corpus.jsonl。分类标签直接读取gold；详细接入说明见[../TRAINING_GUIDE.md](../TRAINING_GUIDE.md)。

这30条示范用于质量检查，PMC16条用于单独的小规模自然引文诊断。保持原Sarol Train/Dev/Test划分；新样本单独报告结果。PMC16条中不准确和无关各只有1条，下一批自然引文重点补足这两类。

## 陈明进

请把训练、验证、测试脚本改为读取上面的三个claims文件和同目录corpus。微调评估的第1类与训练一致，使用IRRELEVANT；无检索候选另记弃权并保留在总分母。对应代码为code/cmj/run_task4_finetune.py、run_task4_eval_dev.py、run_task4_eval_test.py。

用新Train重新训练，Dev固定设置后再评测Test。上传完整运行命令、数据版本与提交号、训练日志、三类precision/recall/F1、Macro-F1、混淆矩阵和全部606条逐条预测。旧实验保留作为对照。

## 李云

请改code/ly/build_sarol_retrieval.py，直接读取新claims、corpus和gold，替换从旧annotations.zip恢复标签的部分。需要mapping表时读取sarol目录的新gold_mapping-train/dev/test.csv。

先重跑Dev的真实证据与检索证据对照，上传运行命令、数据版本、证据召回、三类指标和错误案例。重点检查不准确类被错判准确或无关的样本，以及弃权样本。两人的主数据版本、类别名称和评测分母保持一致。
