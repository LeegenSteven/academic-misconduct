# 路线一 PDF 统一入口：输入接入检查

2026-10-20。本版本完成本地输入接入与位置复查，尚未实现模型运行、独立解释生成及最终人工验收。不要把此入口的运行成功写成 PDF 闭环验收成功。

## 当前输入

使用已经交给陈明进的不可变来源包 `路线一PDF20点_来源与被引检索交接_20261020.zip`。解压后有 `case_manifest.jsonl`、`pair_manifest.jsonl`、`scope_lock.json`、`sources/` 等。保留来源包，输出另放新目录。

固定 20 个物理引用点、10 对 PDF、16 份不同 PDF。点的身份由施引 PDF 哈希、物理引用标记跨度、被引 PDF 哈希决定。重新运行、增加证据、增加模型不增加点数。该批自动分句仍需人工核对引用范围，不能将机器分句当成双方签字。

## 使用

仓库根目录执行，路径替换为实际位置：

```bash
python code/ly/run_route1_pdf_v3.py \
  --source-root /path/to/路线一PDF独立清单_20261020 \
  --output-dir /path/to/new_pdf_preparation
```

需要 PyMuPDF **1.28.2**。如安装在独立目录可加 `--pymupdf-dir /path/to/dependencies`。版本不符会停止，因为本批原始字符偏移必须可复现。程序不导入 torch，不连接 A100，不访问网络，也不执行训练或推理。

`逐条状态.txt` 用于直接阅读；JSONL 为完整记录；CSV 是状态摘要，原始证据文本以 JSONL 为准。`preparation_receipt.json` 登记来源哈希、程序与冻结 prompt 源码哈希、输出哈希和实际检查数量。

## 被引检索回填接口

`cited_return_template.jsonl` 是接入格式草案，不表示陈明进已经采用该格式。无需重新发一次来源包；回传若采用其他结构，另写明确的转换器并保留原文件。

回填可只含已完成的点，未回填点仍保留在固定 20 点输出中。`case_id`、`pair_id`、`cited_pdf_sha256` 与来源包一致；不认识的 ID、重复 ID、换 PDF 都停止。每行包含：

- `schema_version: route1_cited_pdf_return_v1`；`retrieval_status` 为 `pending`、`ok` 或 `no_reliable_evidence`。
- 实际 `producer`、`retrieval_completed_at`；固定 parser 为 PyMuPDF 1.28.2。
- `retrieval_config` 记录实际 method、version、query、top_k、corpus_pdf_sha256。检索池只允许该被引 PDF；这里不替陈明进指定算法或 top_k，模板相应参数先留空。后续按双方固定的检索设置和 tokenizer 预算接入，不静默截断证据。
- `candidates` 每条有原始 evidence_id、source_pdf_sha256、text、pdf_fragments。`text` 必须是各原文片段 raw_text 按 `\n` 连接的结果，不可改数字、主体或条件。技术接入不等于语义支持。
- `pdf_fragments` 与来源包片段字段相同：PDF 页码从 1 开始；char_start/char_end_exclusive 按 `page.get_text("text", sort=False)` 的 Unicode 码点，零起始半开区间；保留 raw_text、raw_text_sha256；source_blocks 是所有相交文本块的 block_number 和 bbox（PDF 坐标单位为点，左上原点）。bbox_scope 必须注明整块边界，不冒充精确句框。printed_page 不能确定时为 null。
- `no_reliable_evidence` 需要 note 并保持 candidates 为空；不能因此自动填 IRRELEVANT。

加入回填再次执行：

```bash
python code/ly/run_route1_pdf_v3.py \
  --source-root /path/to/source_package \
  --retrieval-return /path/to/original_or_converted_return.jsonl \
  --output-dir /path/to/another_new_preparation
```

回填证据通过机器回放后，生成的 `classification.provisional.inputs.jsonl` **仅为草稿**，并非正式可运行输入。当前引用范围仍待核对，程序没有 model-run 子命令，也不据此调用模型。模型可见部分复用冻结的 system/user prompt 格式，不加入 gold、双方标签或裁决。原 prompt 的 confidence 请求不代表概率已校准；导出接口三类 score 和 confidence 继续为 null。

## 后续接通与验收

核对引用范围、接入真实被引检索返回后，再准备 A100 小批运行。领域及 adapter 必须在推理前选定；本批按已有领域记录选择 Mbio checkpoint-100，不能看预测后切换模型。固定 adapter 权重 SHA-256：

`0f4019af9d0f510408f841797c1038bb19abfee8b6e5f24dc7f222501776bd09`

分类响应只含 label 可用于分类。解释模块必须单独运行并记录实际底座/adapter 身份、输入哈希、原始响应和 GPU 环境；不能用程序补齐字段伪装模型解释。解释所选证据必须回到被引 PDF；模型输出不得改写双方原始判断或最终裁决。

本入口保留四项指标为空或未运行：工程闭环、定位有效性、解释语义、分类正确性。定位有效性仍以预定 20 点为分母，需人工确认至少 16 点有效才达到 0.80；目前的 20 点机器位置回放不能替代这个数字。无 gold 时不输出分类准确率。

不改变冻结 v2 数据、prompt 源文件、6 个 Test 结果、旧路线二共享样本或陈明进的检索实现。

## 回归检查

```bash
python code/ly/test_route1_pdf_v3.py --source-root /path/to/source_package
```

测试读取真实 PDF，但临时构造的检索返回只用于验证字段与拒绝错误路径，不是人工标注、语义判断或真实检索实验。测试临时文件不会混入正式结果。
