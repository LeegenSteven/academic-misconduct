# Sarol v2 数据包与校验说明

本包沿用已冻结的 quality_v1 数据和 v1 BM25 top-10 **句子**检索，不重新划分样本、不修改标签、不使用 gold 选择候选。此次修正模型提示词中的追踪编号，并生成标签独立旁路，供统一训练与评测使用。

## 可直接使用的文件

每个 split 均有 `{split}.inputs.jsonl` 和 `{split}.gold.jsonl`，两者的 `claim_id` 逐条、同序对齐。一个 split 内 ID 唯一；跨 split 的 ID 可以重复，汇总时须使用 `(dataset, split, claim_id)` 联合键。

| Split | 样本数 | ACCURATE | NOT_ACCURATE | IRRELEVANT | 每条候选证据数 |
|---|---:|---:|---:|---:|---:|
| Train | 2141 | 1368 | 630 | 143 | 10 |
| Dev | 316 | 191 | 101 | 24 | 10 |
| Test | 606 | 386 | 170 | 50 | 10 |

模型只接收 `system_prompt` 和 `user_prompt`。不要将整条 JSON 输入模型。外部 `claim_id`、`candidate_evidence` 中的真实文档与句子位置，以及 `.gold.jsonl` 内的标签/原始证据，只用于结果关联、训练监督或评分。

`input_sha256` 只覆盖模型可见的 system/user 两个字段，使用 UTF-8、JSON `ensure_ascii=False`、`sort_keys=True`、`separators=(',', ':')` 后求 SHA-256。ID 和其他外部 metadata 不参与该哈希。

## 已完成的机器校验

1. `corpus.jsonl` 与三个 `claims-*-model.jsonl` 的文件大小、SHA-256 均与冻结 v1 manifest 完全一致。
2. 使用相同分词、BM25 参数（k1=1.2，b=0.75）、候选原序及并列分数处理，重建三个 v1 输出。三份完整 JSONL 的字节长度和 SHA-256 均与 v1 manifest 完全一致，证明原始候选、排序、紧凑编号、文本及映射未改变。
3. v2 仅从 user prompt 删除 `claim_id: ...` 行和证据行中的 `doc_id=...` 字段；system prompt 保持 v1 原文。候选继续使用 `Dxx:Sxx` 紧凑编号。
4. 检索函数只接收引用论断、`cited_doc_ids` 和 corpus；gold 与人工证据不进入检索接口。
5. 每个 split 的输入、gold、源记录的 ID 与顺序完全一致，标签均属于三分类，源 `training_label_ready` 均为 true。
6. 每条候选恰好 10 条，编号唯一且合法，无缺失候选样本；v2 user prompt 没有程序插入的追踪或 gold 字段前缀。
7. 输出重新读回并与内存记录完全比较。逐文件大小与 SHA-256 保存在 `manifest.json`。

没有运行模型推理，没有以 Test 结果调整提示词或检索规则。

## 保留的原始标注状态

本次没有补造或修订原始 gold evidence。源数据的 `evidence_missing` 为 true 的记录分别有 Train 442、Dev 61、Test 119 条；另有 Train 4 条为 `label_resolved_source_ambiguous`。这些状态已逐条保留在 gold 旁路中，标签保持源数据版本。缺失或歧义的 gold evidence 不应作为精确证据监督的真值使用；三分类监督使用已确认的 `label`。

corpus 共 8515 条文档记录，没有空白 abstract 句子，因此 v1 的空白句过滤不会导致本包源句位置偏移。模型证据位置映射沿用原 v1 定义。

## 可复现生成

在仓库根目录执行：

```powershell
python code/ly/build_sarol_inputs_v2.py --source-dir data/quality_v1/sarol
```

源数据如放在其他位置，可以只修改 `--source-dir`；manifest 仍记录稳定的仓库逻辑路径。生成器仅依赖 Python 标准库，任何源文件哈希或 v1 重建不一致均中止。重新生成会覆盖当前 v2 文件，因此请先保留已用于实验的冻结版本。

reasoning 关闭应由实际训练/推理的 chat template 参数落实，本数据文件不会替代该运行配置。
