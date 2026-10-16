# 路线一 v2：李云 Mscv 训练与 Dev 阶段记录

记录日期：2026-10-16。数据包为 `results/route1_qwen38_v2/2026-10-15/`。下列运行输出和文件哈希来自 A100 终端及其生成的指标文件；训练产物、预测 JSONL 和已有运行日志仍在 A100，尚未复制进本仓库。前台运行的完整 stdout 不一定单独留档。

## 当前状态

- v2 静态校验通过：`passed_static_validation_no_model_run`；SciCiteVal 的 10 条冲突继续隔离。
- SciCiteVal Train713 的 tokenizer/mask 检查通过：713 条，监督 token 共 6,947；输入 SHA-256 `4f7357e0022a2e557cb9912f7612699a496d02753451a06b14e2e004f8d3622b`，gold SHA-256 `5a80ff6c6cf813c8256827c63da5ee3c277607afa48f243a9b6743ec4d7be83a`。
- 单卡 GPU smoke 使用 Train 中的 32 条样本，完成真实训练、adapter 保存与独立重载推理：26/32 正确，Accuracy 0.8125，Macro-F1 0.8666666667，无效输出 0。该分数仅用于工程检查。
- 正式 Mscv 从官方 HF 底座独立训练 SciCiteVal Train713：1 epoch，45/45 步，训练耗时 49.31 分钟，train loss 0.1862243065。`checkpoint-45` 与 `final_adapter` 的权重和 adapter 配置哈希分别一致。正式 adapter 另在新进程中完成单条 Train 样本的重载推理。
- 官方 HF 底座与 Mscv 已取得两个领域四个 Dev 单元的**标签分类分数**。Mbio 在两个领域的 Dev 单元待陈明进交付正式 adapter 后补齐。尚未运行 v2 Test。
- 独立的两篇 PDF 演示已完成引用点与被引证据定位，并用正式 Mscv 完成单条标签推理：输出 `ACCURATE`，与人工演示参考标签一致；原始模型输出只有 `label`，没有证据编号和理由，故完整解释字段仍待解决。此样例不计入正式 Dev/Test。详见 [PDF 演示记录](pdf_demo_sciciteval_scifact/README.md)。

## Dev 结果

全部使用 v2 输入、`max_length=4096`、`max_new_tokens=512`、`enable_thinking=False`，不自动重试；现有评测器将无法解析标签的输出计为错误。以下分数只评估标签分类，**不代表完整 JSON 响应符合提示词要求**。结果来自正式 HF 底座及独立 Mscv adapter，不能与历史 GGUF 预跑视为相同配置。

| 数据集 | 模型 | 正确/总数 | Accuracy | Macro-F1 | 无效输出 | 预测 SHA-256 |
|---|---|---:|---:|---:|---:|---|
| SciCiteVal Dev | M0 | 41/54 | 0.7592592593 | 0.7846560847 | 0 | `8ca65bef3b016e7454b9e2373c9be55faea7c9ddb3632c5ee96c762ae904bb0f` |
| SciCiteVal Dev | Mscv | 43/54 | 0.7962962963 | 0.8518518519 | 0 | `9e9eec0ee5a2afd8ffb4f4e08c706e33ba95f88a2178311290a9a669545d6249` |
| Sarol Dev | M0 | 182/316 | 0.5759493671 | 0.5399109634 | 0 | `0983101f23347718fa56b366239551ab2d12dbb25c17162dd227640acdb3d92a` |
| Sarol Dev | Mscv | 199/316 | 0.6297468354 | 0.6269599260 | 0 | `cc0a7d7e4137351ef0478e42005ed8684c7547ae19c9bb60e494d547bc29dbf2` |

同域比较：SciCiteVal 上 Mscv 比 M0 多答对 2 条，Macro-F1 高 0.0671957672；Sarol 上多答对 17 条，Macro-F1 高 0.0870489626。Sarol 的 Mscv 仍将 88 条 `ACCURATE` 误判为 `NOT_ACCURATE`，需要保留逐条预测做后续误差分析。SciCiteVal Dev 仅 54 条，其中 `IRRELEVANT` 4 条，不能仅凭这批数据推断泛化幅度。

### 响应字段审计（2026-10-16）

对四组 Dev 预测文件逐条解析 `raw_output` 并统计字段：M0 的 SciCiteVal 54/54、Sarol 316/316 含有 `label`、`evidence_ids`、`reason`、`confidence` 四字段；Mscv 的 SciCiteVal 0/54、Sarol 0/316 含有四字段，**370/370 条均仅有 `label`**。这一步只检查字段是否出现，尚未证明 M0 的字段值、证据编号与候选输入完全合规。独立的 [响应 schema 审计脚本](../../../code/ly/audit_route1_dev_output_schema_v1.py) 可进一步核查字段类型、证据编号范围、理由长度和置信度；审计不得修改原预测或既有标签分数。

原因可在当前冻结训练代码中复核：assistant 目标被构造成 `{"label": ...}`，现有评测器也只用 `parse_label` 打分。因此 `invalid_count=0` 只说明标签可解析，不能解释为完整输出 schema 无效数为 0。**在响应方案及评测规则确认前，Mscv 不能按完整引用判定输出验收，也不应启动 Test。** 需要与路线一负责人确认是保持“标签分类”和“证据理由”分阶段交付，还是另建含证据与理由监督的数据/adapter 版本；不可把人工理由或输入证据编号回填成模型原始输出。

两模型在同一领域内的输入和 gold 哈希一致：

| 数据集 | Dev 输入 SHA-256 | Dev gold SHA-256 |
|---|---|---|
| SciCiteVal | `93df53e04a249bd4a83fbc739db87ae88fee59b842eee8d6daa162d9efe328b1` | `9e182bbf8a274ca044c988ae8bebb2507178153ba19ce190a1451feac89c5b50` |
| Sarol | `2c0690ab3a0c50cc63c47bf0db06f63895de51513d1257ecf4aeb051d1e64403` | `d1d0362dba636ea5c93803c50671ca822bd5c1cd058db10bc261eda6386823c4` |

## Mscv 产物与哈希

- 官方底座目录：`/home/admire/models/Qwen3.8-27B`；`config.json` SHA-256 `191e0af232104ed8b65258cf3fb2b842e288008baca7633c11b82a1ac7203aab`。
- 训练目录：`/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/route1_qwen38_v2_train_20261016_gpu3/train/Mscv/`。
- `checkpoint-45/adapter_model.safetensors` 与 `final_adapter/adapter_model.safetensors` SHA-256：`5d9be2027cf3de78f4df6a89564dab9b3cf970c0d7b9917a4f965b8e88e8bf54`。
- 两处 `adapter_config.json` SHA-256：`bbc4d950e74884df8b07f82b2ecf588f936b9a7a46284724f22130b1773637a1`。
- `training_config.json` SHA-256：`011bdfc438071198b513eae738890549b8c7f98b044b4cf592a256289f838a54`。
- 训练脚本已恢复为 v2 包 manifest 锁定内容，SHA-256 `606f70300d8039d6dd84e9cfa565b39616b3368df5d2e4c13058ad783e8ac0fa`；A100 上的 v2 静态校验随后通过。
- LoRA：r16、alpha32、dropout 0.05，学习率 1e-4，micro-batch 1、梯度累积 16、seed 42；监督范围为 assistant JSON 标签及轮次结束标记。

## 待完成

1. 获取陈明进从同一官方底座独立训练的 Mbio adapter，完成 Mbio × SciCiteVal/Sarol 两个 Dev 单元，凑齐 6 个 Dev 单元。
2. 与路线一负责人确认完整响应 schema 的处理方案，核验四组现有 Dev 输出的字段值；待六个 Dev 单元完成后选择两个正式 checkpoint，并冻结输入哈希、模板、长度、精度、解码和解析规则，之后才启动 Test。
3. 将 A100 上现有的训练日志、四组 Dev 原始预测与指标文件复制到交付目录，核对本记录的哈希；adapter 权重留在合适的模型存储位置，不直接提交到普通 Git 仓库。
4. 两篇真实 PDF 的引用关系匹配、施引位置、被引证据定位与 Mscv 标签判定已经接通。需确认并实现模型输出 `evidence_ids` 和 `reason` 的方案，再验收完整解释闭环；此前 PointRend 与 DySample 的单文档索引 smoke 不能替代该闭环。
