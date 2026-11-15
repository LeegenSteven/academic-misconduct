# Mbio 错引识别 Dev 执行清单

2026-11-10｜李云整理，供陈明进核定后续实验设计。已用两组归档预测完成离线基线核对。下文实验顺序和晋级规则为讨论稿。

## 现有 Dev 基线

比较同一次纠正训练的两个 checkpoint，使用 Sarol Dev 全部 316 条。以 `(dataset, split, claim_id)` 关联冻结输入、gold 和两组预测，逐条核对 gold，按归档指标文件核对三类输入文件的 SHA256（输入、gold、各自预测）。两组均使用 5120/512、关闭 thinking、保留首次响应。原实验按 Macro-F1 选中 checkpoint-134。

| 纠正训练 checkpoint | 判对 | Macro-F1 | NOT_ACCURATE 正确/总数 | NOT_ACCURATE 召回 | 该类误报数 | 无效输出 |
|---|---:|---:|---:|---:|---:|---:|
| 100 | 218/316 | 0.566507 | 56/101 | 55.45% | 52 | 0 |
| 134 | 222/316 | 0.596966 | 43/101 | 42.57% | 32 | 0 |

两者都识别出的错引有 43 条，仅 100 识别出的有 13 条，仅 134 识别出的有 0 条，两者都漏掉的有 45 条。该比较描述同批记录上的预测差异，不能分解训练损失的因果效应。

## 候选可见性

每条输入有 10 个候选。逐条核对 `evidence_id | text` 出现在实际提示中，再以 `(doc_id, sentence_id)` 匹配冻结 gold 的去重标注句。可见只表示候选中出现了该标注句。两组预测在同一份输入上比较。

| 冻结 gold 与候选的关系 | 全部条数 | 其中 gold 为错引 | 100 识别出的错引 | 134 识别出的错引 |
|---|---:|---:|---:|---:|
| 至少一个标注句可见 | 146 | 29 | 13 | 9 |
| 有标注文档，候选未含标注句 | 38 | 11 | 3 | 2 |
| 全部标注文档均未进入候选 | 71 | 24 | 12 | 10 |
| 冻结 gold 无可匹配句级标注 | 61 | 37 | 28 | 22 |
| 合计 | 316 | 101 | 56 | 43 |

255 条有句级标注，146 条至少命中一句，109 条可按文档或句子环节排查。61 条可按原分类 gold 计分，其句级可见性无法判定。[316 条逐 ID 明细](Sarol_Dev_候选可见性逐条核对_20261110.jsonl)保留匹配数、候选编号和两组预测。

## 实施顺序与停止条件

1. **先固定数据和规则。** 主比较沿用 Sarol Dev 的 316 个 ID、三分类、现有解析、无效输出计错、参数与分母。登记候选生成规则、允许的改动、候选上限、检查点、两个主指标、并列规则和试验次数，交陈明进共同核定。若 ID、gold 或预测哈希对不上，先停止比较并查来源。
2. **先诊断候选。** 对 71 条文档缺失与 38 条句子缺失，分别检查检索和句子选择。拟议的实际检索策略须能仅凭施引输入及检索语料生成候选。若要测试“人为加入 gold 标注句”的上界，单设诊断条件，其结果仅用于衡量覆盖缺口。无标注的 61 条单列。所有总体分类指标仍以完整 Dev 为分母。
3. **再核对完整主张。** 对标注句可见而仍漏检的记录，从错引类型中按原句核对象、方向/否定、数值/范围、时段、方法和归属，分别保存可定位证据与未覆盖限定。若后续比较提示词改动，固定 checkpoint 和候选，用同一批 ID 配对，仅改变判定提示。按候选实际可见内容审核，待核项保留。
4. **双指标比较。** 同表报告 Macro-F1 和 NOT_ACCURATE 召回（TP/101），附三类 P/R/F1、混淆矩阵、无效数，以及错引找回和新增漏检的逐 ID 配对数。观察召回增加时，同时报告被误报为错引的 ACCURATE 和 IRRELEVANT 各有多少条。
5. **晋级与停止建议，待核定。** 新候选与现行 checkpoint-134 的 Dev 基线比较。建议先筛 Macro-F1 至少持平、错引 TP 高于 43 的候选，再按错引召回、Macro-F1 顺序择优；如并列，优先沿用已有配置。未达条件或两个指标出现取舍，报告实际差值和错例，停在 Dev 供裁决。比较用未四舍五入的数值。此次基线已知，这项建议用于将来预先固定的比较；最终门槛和预算由两人核定。采用通过核定的配置后才考虑新运行。本轮只完成离线准备。

## 可复核来源

- [Sarol Dev 输入与 gold 所在目录](../_route1_test_pair_publish_20261019/results/route1_qwen38_v2/2026-10-15/sarol/)，文件为 `dev.inputs.jsonl`、`dev.gold.jsonl`。SHA256 分别为 `2c0690ab3a0c50cc63c47bf0db06f63895de51513d1257ecf4aeb051d1e64403`、`d1d0362dba636ea5c93803c50671ca822bd5c1cd058db10bc261eda6386823c4`。
- [两组 Dev 预测和指标](../_route1_test_pair_publish_20261019/results/route1_qwen38_v3/2026-10-25/mbio_reproduction/corrected_20261031/dev_selection/)。100、134 的预测 SHA256 依次为 `5918c9042c5ff7760fe6f39c5155488500df08ba7c4aaa2109d9f2bfff53b127`、`cad9c96c4355e1c174934a7440f0c7f44bbf3129caa73312f3da6a455e0336ff`。
- [陈明进的归因分析与改进建议](../11.2-11.8/陈明进_错引漏检归因分析与改进建议_20261108.md)。其中 Test 的 6/7/15 属于历史错误诊断。阈值、候选策略及晋级均只使用开发阶段材料，冻结 Test 保留作历史评估。

## 2026-11-13 Gold 依据追踪回传

陈明进回传 [15 条 gold 依据追索结果](gold追踪/发给李云_15条gold依据追索结果_20261112.md) 及对应 Excel。15 条均为原始 `ETIQUETTE`，项目映射为 `NOT_ACCURATE`；冻结 gold 的 `gold_evidence` 均为空，`evidence_missing=true`，诊断状态均为 `NO_ANNOTATED_SENTENCE_AVAILABLE`，当前状态统一为 `PENDING_SOURCE`。

这15条属于冻结 Test 中 `ETIQUETTE` 类的结构性缺证现象：全 Test 共73条 `ETIQUETTE`，其中70条无句级 evidence、3条有 evidence。该类别仍有带证据反例，因此只能登记为“本批未提供句级依据”，不能推断为该类别不需要证据，也不能用候选句反推或改写 gold。

追索动作调整为向原始发布包索取 `ETIQUETTE` 判定记录（claim、被引文献、判定说明）；若原始包也只有 mapping，则登记 `PENDING_SOURCE`。本回传不修改冻结 gold、原始标签、模型输出、Test 成绩或15条的项目标签。

## 2026-11-13 ETIQUETTE 原始判定记录核查回执

陈明进回传并核对了 Sarol 原始发布包：其说明为 7 个包内成员，包含 3 个 `gold_mapping` CSV 和 4 个 BM25 输入文件，没有 annotation；`gold_mapping-test.csv` 只有 `claim_id`、`raw_label`、`project_label` 三列，没有 claim、被引文献编号或判定理由。该原始发布包的 SHA256 由回执记录为 `db4951e93208614d3d1aace2f925faa6c48a220d5663f6e0e8dfa7126212ae47`；本次回传压缩包本身 SHA256 为 `0f80496371bee4e49e9be7230694f1f8f8962db7e1377b2c22d7cb98ad4bdc4c`，解压后的 Markdown 和 Excel SHA256 分别为 `fb38f3d11eb9990dd8e6b4e616c53df5f0e52a320c6617fe7fd42dbdc43729d6`、`f58f5c1ea10bd46df9a1953bf20daed4eb8b94a6436f35aac2237eacd2c6c691`。

本地对回传 Excel 的核对结果：15 条记录、15 个唯一 `sample_id`，与此前 `发给李云_15条gold依据追索结果_20261112.xlsx` 的 15 个 `citation_id` 集合一致；15 条均为 `raw_label=ETIQUETTE`、`project_label=NOT_ACCURATE`、`gold_evidence={}`、`evidence_missing=true`、`annotation_record=无`。此前 15 条状态均为 `PENDING_SOURCE`，本回执与其一致。

登记结论：本批 15 条继续保持 `PENDING_SOURCE`。不修改冻结 gold、原始标签、模型输出、Test 成绩、joint 或 score。候选 `doc_id` 仍只是 BM25 候选，不能替代原始 `cited_doc_ids`；若上游只能提供 mapping，则记录为“无 annotation，仅有 mapping”，后续不再据候选句补写判定理由。

## 2026-11-13 错引 Dev 改进与验收指标回传

陈明进回传的 Dev 方案已解压核对，包含 Markdown 和 Excel。该方案使用 Sarol Dev 316 条，Test 不参与选点；提出 E1 双门槛选点、E2/E3 训练侧改进、E4/E5 候选检索改进和 E6 Dev 后处理校准，并建议以 Macro-F1、NOT_ACCURATE 召回、ETIQUETTE 召回及 ACCURATE 召回共同观察。当前 ckpt134 的综合指标高于 ckpt100，但 NOT_ACCURATE 召回低于 ckpt100。

本回传登记为陈明进提出的 Dev 改进方案和建议门槛，不视为已批准的新训练或新推理配置。后续仍需两人确认最终实验范围、预算、门槛和停止条件；在此之前不启动 E2/E3 训练、不用 Test 选规则、不改冻结 Test。

回传包 SHA256：`97506f56fe7866bf4d79439e0c684cdf189d863bea7ddbf0e97adf7edbcce051`。解压后的 Markdown SHA256 `05a4028de29b98af9f942a53f6f661da0e7876a7f8a3207cb63cfcf3687cdf7b`，Excel SHA256 `8879a44c0e95d608a1d241b7ed3dc3f92f78810a72bc940b3fcad1466800d486`。


## 2026-11-14 陈明进确认 E1–E6 范围

陈明进已确认按 E1–E6 登记实验范围：E1 先扫描已有 checkpoint，不重训；E2/E3 训练侧排在 E1 结果之后并等待算力窗口；E4/E5 只处理受影响的9条及同族样本；E6 只在 Dev 做后处理校准。建议门槛继续登记为 Dev Macro-F1 ≥0.5970、NOT_ACCURATE recall ≥0.5545、ETIQUETTE recall ≥0.70、非 ETIQUETTE NA recall ≥0.44、ACCURATE recall ≥0.80、无效输出为0；这些门槛待 Dev 可达性确认后定版。预算不超过6组配置，seed固定为42，连续3组未同时改善 Macro-F1 与 NOT_ACCURATE recall 即停止该路径。

本次是实验范围和讨论门槛的确认，不代表已批准新训练或 Test。下一步先完成 E1 的已有 checkpoint 扫描；在门槛定版前不启动 E2/E3，不改冻结 Test。15条 ETIQUETTE 继续单独保持 `PENDING_SOURCE`。

## 2026-11-14 E1 结论与后续路线确认

陈明进进一步确认：现有 checkpoint 仅有 100 和 134，双门槛在该集合内不可达；该事实如实登记为“现有集合不可达”，不表述为选点失败，也不降低门槛、不使用 Test 反推。ckpt100 作为 `NOT_ACCURATE` 优先基线，ckpt134 作为 Macro-F1 优先基线，两者均不单独确定为最终模型。

后续按训练侧和检索侧推进：E2 先测试 NOT_ACCURATE 损失加权 1.5 与 2.0 两档，E3 做支持句类／ETIQUETTE／IRRELEVANT 三族分层采样；E4/E5 并行处理受影响的9条及同族样本。预算仍不超过6组配置，seed固定为42，连续3组未同时改善 Macro-F1 与 NOT_ACCURATE recall 即停止该路径。

若算力窗口尚未排定，当前状态登记为“E1 未达标、E2/E3 待资源”，不启动训练、不跑 Test、不修改冻结成绩；15条 ETIQUETTE 的 `PENDING_SOURCE` 继续单独维护。

## 2026-11-14 E4/E5 输入范围交叉核对

对 E4/E5 的“9条及同族样本”做输入核对时发现 ID 命名空间需要先固定：陈明进归因材料中的9条为 28 条错引漏检诊断案例，分组是 29/156/601（标注文档未进候选）、61/253/504（标注句未选入）、385/426/604（标注句可见但仍漏判），其上下文使用的是 `sarol:test` 诊断记录。当前 316 条 Sarol Dev 明细也存在相同数字的 `claim_id`，但对应记录的 split、gold 和预测不必相同，不能直接按数字替换。

因此，E4/E5 在运行前必须先固定：实验使用的 split、9条的正式输入文件、同族扩展规则，以及是否只做诊断而不参与 Test 选点。当前不把 Test 诊断行直接当作 Dev 实验输入，也不据同数字跨 split 合并记录；在输入版本确认前，E4/E5 暂停执行，E2/E3 仍保持待资源。

## 2026-11-14 E4/E5 Dev 输入范围冻结

陈明进已确认 E4/E5 只使用 Sarol Dev，不使用 Test；Test 的9个同号案例仅作方法锚点。正式冻结输入为 `dev.inputs.jsonl`、`dev.gold.jsonl` 和 `claims-dev-model.jsonl`，哈希与冻结目录一致：输入 `2c0690ab3a0c50cc63c47bf0db06f63895de51513d1257ecf4aeb051d1e64403`，gold `d1d0362dba636ea5c93803c50671ca822bd5c1cd058db10bc261eda6386823c4`，标签侧车 `1efc1b9ddb77dbe79f3f80e511449b81c430fdc519652fb8584d39e4fae6cd4a`。

范围已固定为：E4 文档未进候选 24 条；E5 文档可见但标注句未选中 10 条；C 类 27 条作为训练侧观察组，不并入 E4/E5；ETIQUETTE 145、152、159 单列排除。详细 ID、排除项、Test 方法锚点和 ckpt100/134 基线已写入 `11.9-11.15/Mbio_E4E5_Dev范围冻结_20261114.json`，文件 SHA256 为 `4227af77308c31ea8947388269d37b169a3092a3d960c7b3f9b60377cc88b93b`。

当前状态为“范围已冻结、尚未运行”。E4 将在 Dev 的24条上测试候选 top-k 10→20，E5 在Dev的10条上测试候选句选择；不修改 gold、Test、joint 或 score，不使用 Test 选点。模型运行仍等待资源与执行安排。

## 2026-11-14 资源不可用状态

当前 A100/服务器暂不可用。E4/E5 的 Dev 输入已冻结并完成本地准备，范围为 E4 24 条、E5 10 条，top-k=20、BM25 k1=1.2、b=0.75；输入包 `Mbio_E4E5_A100_input_package_20261114.zip` 已生成，但尚未进行模型推理。状态登记为“E4/E5 执行待服务器资源”，不把输入准备计为实验结果。

在资源恢复前，不启动替代模型、不改 checkpoint、不跑 Test。可继续处理的工作限于文档和来源核对：更新51条来源状态、等待15条来源逐条清单、等待 R2EXP25 第19点证据，以及整理本周阶段交付；这些工作不改变 gold、joint、score 或冻结成绩。

## 2026-11-14 E4/E5 冻结配置与恢复后执行顺序回执

陈明进确认：A100 暂不可用期间暂停 E2、E3、E4、E5，不用 CPU 或小样本替代；E1 已关闭，现有 ckpt100/134 均未同时达到双门槛，不降低门槛、不用 Test 反推、不改既有结论。服务器恢复后先执行 E4/E5，再视资源执行 E2/E3；E4/E5 未出结果前不启动新的训练调参。

E4/E5 固定使用 sarol:dev，正式输入和 gold 哈希保持现有冻结值，E4 全量24条、E5全量10条，C类观察组27条另列，ETIQUETTE 145/152/159排除；不触碰 Test 的9条诊断行。top-k=20属于本轮扩展检索配置，与原输入的 top-k=10 分开登记，不回写原 dev.inputs.jsonl；扩展仍限于各样本 cited_doc_ids 池内，并需保存新增候选句、段落坐标和生成时间。

恢复前需补登记 top-k=20 检索配置及运行包文件名、字节数、SHA256；未登记前不视为配置已核验。运行失败保留完整日志，不用部分结果替代全量。此回执不表示 E4/E5 已完成，不修改 gold、个人标签、模型输出、Test、joint 或 score。回执原件 SHA256：$h。

## 2026-11-15 E4/E5 运行包元数据预核

已核对本地冻结输入包 `Mbio_E4E5_A100_input_package_20261114.zip`：文件大小 64,777 bytes，SHA256 `59bf9d92f950380899a07218c7011765338b296baab9aaf723f2463845829e08`。包内 `manifest.json` 明确记录版本 `route1_mbio_e4e5_inputs_top20_20261114`、split `sarol/dev`、retriever 为 Frozen v1 grouped BM25、`top_k=20`、`k1=1.2`、`b=0.75`；E4 输入24条、E5输入10条，输入与 gold 哈希均已列明。包状态仍为 `prepared_not_run`，没有模型推理，不代表实验完成。

该元数据可在服务器恢复后作为启动前核验依据；运行前仍需保留完整日志、退出码和逐条结果。
