# Sarol 2024 数据字段与标签映射说明

整理人：陈明进  
整理日期：2026年9月2日  
数据来源：ScienceNLP-Lab/Citation-Integrity

## 1. 数据版本和文件位置

本项目涉及三种数据格式，不能把它们当成同一个文件的不同名字。

本地仓库：

`D:\引文不端\项目数据与代码\Citation-Integrity-main`

### 1.1 原始人工标注

文件：

`Data\annotations.zip`

压缩包中每一个 `citations/*.json` 文件代表一条引用实例。它保存最完整的人工标注信息，包括引用上下文、被引证据和原始标签。

### 1.2 引用上下文识别数据

文件：

`Data\train.jsonl`  
`Data\dev.jsonl`  
`Data\test.jsonl`

每个非空行代表一条上下文识别样本，主要由 `sentences` 和 `labels` 组成。`labels` 与 `sentences` 按位置对应，1表示该句被标为目标引用上下文，0表示不是目标上下文。

### 1.3 MultiVerS格式数据

目录：

`Data\multivers-format`

主要文件为：

- `claims-train.jsonl`
- `claims-dev.jsonl`
- `claims-test.jsonl`
- `corpus.jsonl`

`claims-*.jsonl` 用于证据检索和最终分类，`corpus.jsonl` 是被引文献候选语料。正式claim数量为 Train 2,141、Dev 316、Test 606，合计3,063条。

## 2. 原始人工标注字段

原始JSON的一条记录包含以下字段：

### 2.1 `citing_paragraph`

引用所在的完整段落，来自引用论文。它可能包含多句话和多个引用标记，主要用于保留上下文背景。

### 2.2 `citation_context`

人工标出的、与目标引用直接相关的上下文片段。每个片段通常包含：

- `text`：引用上下文文本；
- `start`：片段在 `citing_paragraph` 中的起始字符位置；
- `end`：片段在 `citing_paragraph` 中的结束字符位置。

分析单条引用主张时，优先阅读这个字段，而不是直接把整段 `citing_paragraph` 当作主张。

### 2.3 `evidence_segments`

人工从被引论文中选出的证据句。每个证据片段通常包含：

- `text`：被引论文中的证据句；
- `start`：证据句在被引文献文本中的起始位置；
- `end`：证据句在被引文献文本中的结束位置。

这些句子是人工判断引用是否得到支持的依据，也是后续计算证据检索Recall的金标准。

### 2.4 `marker_span`

目标引用标记在完整段落中的位置，通常包括：

- `text`：引用编号或编号范围；
- `start`：起始字符位置；
- `end`：结束字符位置。

它用于定位“这一条引用到底对应段落中的哪个引用标记”。

### 2.5 `label`

人工对该引用实例给出的细粒度完整性标签。它不是证据句的标签，而是对“引用主张与被引证据之间关系”的判断。

## 3. 上下文识别JSONL字段

外层 `train/dev/test.jsonl` 的典型结构如下：

```json
{
  "sentences": ["句子1", "句子2", "句子3"],
  "labels": [0, 1, 0]
}
```

字段含义：

- `sentences`：从引用论文段落中切出的句子列表；
- `labels`：与句子列表等长的0/1数组；
- `1`：该句被标为目标引用上下文；
- `0`：该句不是目标引用上下文；
- `<CITATION_MARKER>...</CITATION_MARKER>`：目标引用标记的位置提示。

这套文件的任务是“识别哪句话是引用上下文”，不是最终判断引用是否准确。

## 4. MultiVerS claim字段

`claims-*.jsonl` 中一条claim的典型字段为：

```json
{
  "id": 0,
  "claim": "引用主张文本",
  "evidence": {
    "66001": [
      {"sentences": [9], "label": "ACCURATE"}
    ]
  },
  "cited_doc_ids": [66000, 66001]
}
```

字段含义：

- `id`：claim编号；
- `claim`：用于检索和分类的引用主张；
- `evidence`：按被引文档编号组织的人工证据集合。`sentences`中的数字是该被引文档的句子编号；
- `cited_doc_ids`：该claim对应的候选被引文档编号列表。

一个claim可以对应多个被引文档，也可以在同一个文档下有多组证据。因此逐项统计 `evidence` 标签得到的是证据集合数量，不是claim数量。

`corpus.jsonl` 每行是一个候选文献语料块，主要字段为：

- `doc_id`：文献语料块编号；
- `title`：标题；
- `abstract`：按句子保存的文献文本。

当前文件实测有8,515个语料块和29,365个句子，不能直接称为8,515篇完整论文。

## 5. 原始标签定义

论文的概念性细粒度标签及数量为：

| 原始标签 | 数量 | 含义 |
|---|---:|---|
| `ACCURATE` | 1,863 | 引用主张得到被引证据支持 |
| `CONTRADICT` | 92 | 被引证据与引用主张相矛盾 |
| `NOT_SUBSTANTIATE` | 243 | 被引论文相关，但证据不足以支持完整主张 |
| `IRRELEVANT` | 217 | 被引论文与引用主张无实质关联 |
| `MISQUOTE` | 38 | 对被引研究的内容或结论进行了错误转述 |
| `OVERSIMPLIFY` | 111 | 过度简化导致原意发生重要变化 |
| `INDIRECT` | 82 | 主张可能正确，但被引文献不是该结论的原始来源 |
| `ETIQUETTE` | 417 | 引用规范、归属或学术引用礼仪方面存在问题 |
| **合计** | **3,063** | |

仓库实际字符串中将 `INDIRECT` 拆成了：

- `INDIRECT`：48条；
- `INDIRECT_NOT_REVIEW`：34条；
- 合计仍为82条间接引用。

这个拆分不改变论文层面的概念标签，但在读取和转换数据时必须同时处理两个字符串。

## 6. 八类标签到三分类的正式映射

按照论文建模口径，正式映射如下：

| 原始标签 | 三分类输出 | 处理说明 |
|---|---|---|
| `ACCURATE` | `ACCURATE` | 证据支持引用主张 |
| `INDIRECT` | `ACCURATE` | 论文建模时并入准确类，但保留原始标签用于治理分析 |
| `INDIRECT_NOT_REVIEW` | `ACCURATE` | 仓库对间接引用的拆分，建模时同样并入准确类 |
| `CONTRADICT` | `NOT_ACCURATE` | 证据与主张矛盾 |
| `NOT_SUBSTANTIATE` | `NOT_ACCURATE` | 证据不足以支撑主张 |
| `MISQUOTE` | `NOT_ACCURATE` | 错误转述 |
| `OVERSIMPLIFY` | `NOT_ACCURATE` | 过度简化造成语义偏差 |
| `ETIQUETTE` | `NOT_ACCURATE` | 引用规范或归属问题 |
| `IRRELEVANT` | `IRRELEVANT` | 被引论文与主张无关 |

合并后的总量为：

```text
ACCURATE = 1863 + 82 = 1945
NOT_ACCURATE = 92 + 243 + 38 + 111 + 417 = 901
IRRELEVANT = 217
```

```text
1945 + 901 + 217 = 3063
```

## 7. 两个必须写进预处理规则的特殊点

### 7.1 `INDIRECT` 的保留策略

如果目标只是复现论文三分类，`INDIRECT` 和 `INDIRECT_NOT_REVIEW` 按上表映射为 `ACCURATE`。但是本项目面向学术不端治理，间接引用虽然内容可能正确，仍可能是需要提示的引用来源问题。因此建议：

- 模型训练标签按论文口径映射；
- 原始细标签单独保留；
- 输出阶段同时记录 `is_indirect` 标志，避免治理环节丢失信息。

### 7.2 `IRRELEVANT` 的MultiVerS表示

MultiVerS代码接受的是有证据的三分类标签，以及没有证据时的隐式 `NOT_ENOUGH_INFO`。因此 `IRRELEVANT` 不能只把字符串改名后继续放进 `evidence`。

正确结构是：

1. 保留该claim的 `cited_doc_ids`；
2. 删除该被引文档在 `evidence` 中的证据条目；
3. 让读取器根据“候选文档存在但没有证据”生成隐式无证据状态。

这一步只影响MultiVerS输入结构，不改变原始人工标签。原始 `annotations.zip` 必须保持不修改。

## 8. 当前验收状态

- 数据字段：已完成初版说明；
- 标签定义：已完成初版说明；
- 三分类映射：已形成正式映射表；
- 版本差异：已确认3066与3063的数量差异及发布时间不同，具体3条记录仍待追踪；
- 模型运行：尚未完成，不能将本说明当作模型复现结果。
