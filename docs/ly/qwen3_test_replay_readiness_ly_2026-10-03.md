# Qwen3 Test 复算与校准就绪性核查（李云，2026-10-03）

## 结论

当前不能把这批材料作为 Qwen3 Test 复算或校准输入。目录中的模型身份是 MultiVerS `step2141`，不是 Qwen3；原始预测只有 `claim_id/gold/pred`，没有概率或 logits。Qwen3 复算状态为 **待补材料**，本轮不重跑。

## 已核对结果

- Test 预测：606 条，ID 唯一且连续为 0–605。
- gold 分布：ACCURATE 386、NOT_ACCURATE 167、IRRELEVANT 53。
- pred 分布：ACCURATE 328、NOT_ACCURATE 276、NEI 2；NEI 保持独立类别。
- 两条 NEI：claim_id 196（gold NOT_ACCURATE）、296（gold IRRELEVANT）。
- gold=IRRELEVANT 的 53 条中：预测为 NOT_ACCURATE 42 条、ACCURATE 10 条、NEI 1 条，预测为 IRRELEVANT 0 条。
- 已复核指标：全量 Accuracy 0.5512（334/606）；排除 gold IRRELEVANT 后 0.6040（334/553）；三分类有效记录 604 条，Macro-F1 0.3642。

## 60 条证据定位表

- 文件有 60 行，但 `loc_ok(是/否)`、`ev_ok(是/否/不适用)` 和 `note` 三列均为空。该表目前是待填写表，不能把 README 中的“有效36/不适用3/位置不匹配9/无证据12”当成这份 CSV 已完成的逐条记录。

## 缺少的 Qwen3 材料

- Qwen3 模型/检查点及哈希。
- 同一份 606 条、过采样前 Test 输入及 SHA-256。
- prompt/system/template、输出 schema、解码参数和 seed。
- 执行脚本、环境信息、完整 Qwen3 运行日志。
- 带概率或 logits 的原始 Qwen3 输出。
- 若必须重跑：GPU/资源、预计时间、负责人登记。

## 可以先做的工作

- 先保留这批 MultiVerS 606 条结果作为历史基线，不能改称 Qwen3。
- 继续填写 60 条证据定位表，逐条完成 `loc_ok`、`ev_ok` 和说明。
- 等 Qwen3 材料齐全后，再做同一 Test 的一次性复算；校准前风险分数继续保持 null。

机器可读留痕：`docs/ly/qwen3_test_replay_readiness_ly_2026-10-03.json`。