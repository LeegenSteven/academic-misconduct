# Route1 Qwen3.8 实验冻结配置 v1

确认日期：2026-10-13

本配置依据师兄对本轮实验的确认执行，适用于 M0、Sarol adapter 和 SciCiteVal adapter 的 Dev/Test 评测。

## 统一推理配置

- reasoning：统一关闭（reasoning off）。服务端或请求参数必须显式设置，并在运行日志中确认实际生效。
- prompt：M0、两个 adapter 的 Dev/Test 使用同一版本提示词。
- 精度：统一记录并固定。
- 解码参数：统一记录并固定。
- 输出解析：统一使用同一解析规则。
- 所有输入、配置和输出均记录数量、ID、文件大小和 SHA-256。

## Sarol 输入规则

- Train：2141 条。
- Dev：316 条。
- Test：606 条。
- 对每条引用，从其 `cited_doc_ids` 对应的全部候选文本中提取句子。
- 使用引用上下文对候选句进行 BM25 排序，取前 10 句。
- 候选句不足 10 条时全部保留。
- 不先筛选 20 个候选文档。
- 不读取 gold 或人工金证据来挑选输入。
- Train、Dev、Test 必须使用同一个输入生成程序。

## SciCiteVal 输入规则

- 实验版本 v1 使用隔离冲突记录后的 1024 条数据：Train713、Dev54、Test257。
- 10 条冲突记录保留在待核清单中，不进入本轮 Train/Dev/Test。
- 输入直接使用原始 `Cited_content`。
- 不套用 Sarol 的 BM25 检索规则。
- 冲突记录后续如有修复，另建数据版本，不覆盖本轮 v1 划分。

## 实验顺序

1. 生成新的 Sarol BM25 top-10 句输入，并核验 Train/Dev/Test 的数量、ID 和哈希。
2. 重新运行统一配置下的 Sarol Dev316 M0。
3. 运行 SciCiteVal Dev54 M0。
4. 分别训练 Sarol adapter 和 SciCiteVal adapter，两个 adapter 都从同一个官方 Qwen3.8-27B 底座独立开始。
5. 在 Dev 上选择 checkpoint 并冻结配置。
6. 统一运行 6 个 Test 单元，并保存逐条预测、原始输出、日志、指标、Macro-F1 和混淆矩阵。

## 历史结果说明

历史 Qwen3.8 Sarol Dev316 的 69.30% 使用了不同的证据输入，并且 reasoning 配置存在例外，只作为历史参考，不能与本轮结果直接混比。

## 当前已确认状态

- SciCiteVal v1 的冲突审计、来源核验、分组、Dev 输入、gold 和 manifest 已完成。
- Sarol BM25 top-10 句输入已经生成并核验：Train2141、Dev316、Test606，三份输入每条均保留 10 句，ID 唯一且符合 `D01:S01` 格式。
- 输入目录：`sarol_bm25_top10_inputs_v1_2026-10-13/`。
- 输入生成脚本：`code/ly/build_sarol_bm25_top10_inputs_v1.py`。
- Sarol Dev316 的 BM25 top-10 句、reasoning-off 推理已跑完：共 316 条，输出 316 条且 claim ID 唯一。以下服务器核验结论来自李云回传的命令输出；本地尚未取得本次全部原始输出和运行日志。
- 实际权重路径为 `/home/admire/qwen3_8_runtime/models/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q4_K_P.gguf`，接口别名为 `Qwen3.8`，接口报告量化格式为 `Q4_K - Medium`。该文件名指向社区修改版；尚未核验其来源、权重哈希及其与两个 adapter 官方底座的关系。因此本次暂记为 GGUF Dev 预跑，不能直接确认其为本轮正式 M0。
- 本次预跑标签指标：193/316 条正确，Accuracy `0.6107594937`，Macro-F1 `0.5878729237`；混淆矩阵和逐类指标保存在 A100 的评测目录中。指标按全部 316 条预测标签计算，没有因 `failure_status` 非空而排除样本。
- 8 条输出的 `reason` 超过 120 字，被解析器截断并标记为 `invalid_reason`；对应 ID 为 27、63、64、108、165、177、225、274。补跑后 8 条的标签和证据编号均与首次结果一致，不能据此认定完整 JSON 或 confidence 相同。首次 316 条输出作为本次标签评测来源；补跑单独保存用于复核，无需合并覆盖首次输出或清空错误状态。
- A100 评测文件由历史 `evaluate_qwen3_dev_reanalysis.py` 生成。该脚本硬编码了旧任务名、`reanalysis_completed_no_new_inference`、历史路径提示和待办项；这些元数据不适用于本次运行。评测脚本本身不执行模型推理，但本次预测来自新的服务器推理。正式交付须以本次输入、原始响应、运行日志和实际权重来源重新记录评测来源。
- SciCiteVal Dev54 尚未运行。下一步先核验正式 M0 与两个 adapter 的底座和精度是否一致，再在该统一配置下完成两个 Dev M0；Test606 正式推理仍等待两个 adapter 完成、Dev 选定 checkpoint 并冻结配置。
