# 修复后的Sarol训练数据：两位同学取用说明

版本：2026-10-04 / `sarol-quality-v1`。拉取仓库最新main后，直接读取以下四个文件。

| 文件（均在data/quality_v1/sarol/） | 用途 | 数量 |
|---|---|---:|
| claims-train-model.jsonl | 训练 | 2141 |
| claims-dev-model.jsonl | 验证与选参数 | 316 |
| claims-test-model.jsonl | 最终评测 | 606 |
| corpus.jsonl | 证据检索与句子取回 | 8515段落块、29365句 |

每条引用的分类标签直接读 `gold`，类别为ACCURATE、NOT_ACCURATE、IRRELEVANT。无金证据由 `evidence_missing` 单独表示，不能据此把标签改成IRRELEVANT。8515条corpus记录是100篇被引论文的段落块，doc_id不是论文ID。

新版本按官方原始人工标注修正了39条旧转换错配标签：Train36条、Test3条，Dev不变。官方Train/Dev/Test划分保持不变。Test类别数量为ACCURATE386、NOT_ACCURATE170、IRRELEVANT50。旧实验应保留，这次先用修复后的Train重新训练，再用固定Dev验证，最后评测Test。

## 陈明进接入现有模型

训练脚本 `run_task4_finetune.py` 的 `V2_TRAIN`、验证脚本的 `V2_DEV`、测试脚本的 `V2_TEST`，分别改成上表的三个 `*-model.jsonl`。三份脚本的 `CORPUS` 都指向本目录corpus.jsonl。编码器、checkpoint和输出目录继续使用你机器上的位置。

在code/cmj目录的脚本中，可以这样设置路径（Path已在原脚本导入）：

```python
DATA = Path(__file__).resolve().parents[2] / "data" / "quality_v1" / "sarol"
V2_TRAIN = DATA / "claims-train-model.jsonl"
CORPUS = DATA / "corpus.jsonl"
```

微调模型的第1号分类槽位是IRRELEVANT，目前微调评估代码仍显示NEI，应与训练LABEL2ID对齐；无检索候选另记弃权，并计入评测分母。未微调官方SciFact模型的NEI定义应按其原任务处理。

## 李云取用

训练、评测、风险分析都读取显式gold。本目录的gold_mapping-train/dev/test.csv由修复标签生成，可供现有需要mapping表的评估程序使用。`evaluate_sarol_evidence_block_level.py`的--claims可以指向对应的*-model.jsonl。

旧 `build_sarol_retrieval.py` 依赖multivers-format目录及annotations.zip，接入本版时应改成读取本目录的claims、corpus和gold，不能继续用旧方法恢复标签。请在实验日志中写明版本sarol-quality-v1。

## 文件校验与复现

```bash
python scripts/validate_sarol_training.py
```

这四个训练文件已在仓库内，可直接使用。若要从公开上游重新转换，可运行 `python scripts/repair_sarol_data.py --download`（需Python3.10+、Git和网络）；它固定官方提交并验证标签对齐。模型运行依赖沿用各自现有环境。

来源：[ScienceNLP-Lab/Citation-Integrity](https://github.com/ScienceNLP-Lab/Citation-Integrity/tree/e9823957bb263db9ae402351b76d88ff1a723712)。原仓库的MIT许可文本保存在UPSTREAM_LICENSE.txt；论文文本保留原始来源归属。
