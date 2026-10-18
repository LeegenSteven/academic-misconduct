# 被引全文证据检索端到端原型（陈明进，2026-10-18）

对应师兄 10/16 分工中陈明进主责的「被引 PDF 证据检索」与共同要求的「接通真实两篇 PDF 的引用判定流程」。
本原型把被引文献**全文**（非仅摘要）解析、BM25 检索、v2 模型输入构建、adapter 推理这条链路在两篇真实 PMC OA 文献上打通。

## 一、和冻结实验的关系

- 冻结 Sarol v2 的候选证据只来自被引文献的**摘要句**（原始 `corpus.jsonl` 只有 abstract）。
- 本流程在被引文献 **PMC JATS 全文**（abstract + body 各 sec 段落）上检索，并保留每条候选证据的
  章节（section）、段落序号、段内句序、段内字符偏移，是"被引 PDF 证据检索"的原型实现。
- **不改动任何已冻结数据**。分词、BM25 参数（k1=1.2, b=0.75）、平局规则、system_prompt、
  user_prompt 渲染、`input_sha256` 口径全部直接复用 `code/ly/build_sarol_inputs_v2.py`，
  模型可见格式与冻结实验完全一致（已逐条校验）。
- PMC OA 的标准结构化全文是 JATS XML；PDF 与 XML 是同一篇文献的两种载体，XML 的章节/句位置
  定位比 PDF 更精确。底层解析器 `route1_qwen38_fulltext_retriever_v1.py` 同时支持 PDF（PyMuPDF）和 XML。

## 二、两条真实引用边

| candidate_id | 施引 → 被引 | 主题 | 全文句数 | 引用论断（节选） |
|---|---|---|---:|---|
| PMC-OA-V3-01 | PMC12900525 → PMC10045528 | 牙髓病学生物陶瓷 | 330 | 封闭剂与根尖周组织密切接触，理想材料应生物相容、无毒 |
| PMC-OA-V3-08 | PMC13625197 → PMC9708575 | 神经周网(PNN)与记忆 | 259 | 成年后降解/重塑 PNN 可增强神经可塑性，提升联想/空间/社会/听觉记忆 |

- V3-01 检索 top10 命中多个"生物相容性/密封材料与组织直接接触"句子，与论断高度相关。
- V3-08 的论断是跨章节综述性概括，被引文献分别在 fear conditioning、social memory、
  spatial memory、eyeblink conditioning、ageing 等章节讨论，没有单句完整概括，BM25 top10
  覆盖各相关章节——这本身就是真实引用判定的典型难点。

## 三、产物

| 文件 | 说明 |
|---|---|
| `cited_pdf_demo.inputs.jsonl` | 2 条与 v2 同构的模型输入（system_prompt/user_prompt/candidate_evidence/allowed_evidence_ids/input_sha256） |
| `cited_pdf_demo.locators.jsonl` | 每条候选证据在被引全文的精确定位（PMCID、section、段落、段内句序、字符偏移）+ 源 XML SHA256 |
| `cited_pdf_demo.manifest.json` | 检索配置、源文件哈希、统计、与 v2 的差异、gold 政策 |
| `code/cmj/route1_cited_pdf_retrieval_pipeline_v1.py` | 全文检索 + v2 输入构建脚本（本地 CPU 可跑） |
| `code/cmj/route1_cited_pdf_inference_v1.py` | 无 gold adapter 推理脚本（A100 跑） |
| `code/cmj/_verify_cited_pdf_demo.py` | 独立回读校验脚本（全部通过） |

## 四、本地复现（无需 GPU）

```bash
python code/cmj/route1_cited_pdf_retrieval_pipeline_v1.py
python code/cmj/_verify_cited_pdf_demo.py
```

## 五、A100 上完成引用判定（需李云那边执行）

输入已按 v2 格式准备好，A100 上用冻结的 Mbio checkpoint-100 推理（无 gold，不出指标）：

```bash
python code/cmj/route1_cited_pdf_inference_v1.py \
  --model-path /实际路径/Qwen3.8-27B \
  --adapter /实际路径/Mbio/checkpoint-100 \
  --inputs results/cmj/cited_pdf_retrieval_v1_2026-10-18/cited_pdf_demo.inputs.jsonl \
  --output-dir results/cmj/cited_pdf_retrieval_v1_2026-10-18/inference_mbio \
  --operator 李云
```

输出 `cited_pdf_demo.predictions.jsonl`（逐条 pred、完整四字段 raw_output、输入哈希）和
`cited_pdf_demo.inference_metadata.json`（GPU、环境、adapter 权重哈希）。

## 六、gold 政策与边界

- 这两条边在候选池 `adjudicated_label` 为空，**尚未人工裁决**，故不写 gold、不参与任何指标。
- 正确顺序：模型先给预测 → 双方对原文**独立盲标** → 共同裁决 → 再把裁决标签与预测对照。
- 当前只覆盖 2 条真实边（任务要求"真实两篇"），用于验证流程链路；扩大到批量是后续工作。
- 施引侧 PDF 定位由李云负责，本包只覆盖被引侧全文检索与判定。
