# 两条补充点 A100 执行说明

本目录对应新版“原18点＋两补充点”。两点已冻结，输入和证据定位已生成，但本机没有 A100，当前没有模型响应、日志或退出码。原20点清单、1/15暂缓记录和既有18点结果保持不变。

运行前在 A100 主机核对：

- `official_supplement_manifest.jsonl` 两行均为 `FROZEN_FOR_RUN`；
- `two_point_runtime_plan.json`、`prepared_items.jsonl` 和运行器哈希与本目录收据一致；
- `nvidia-smi` 可见且只有一个选定 GPU，模型底座、18 个权重分片、tokenizer、`Mbio/checkpoint-100` 和依赖版本与已冻结配置一致；
- 输出目录是新的空目录，不覆盖既有运行。

先运行 classifier，再运行 independent explainer。两阶段都要保留 `run_metadata.json`、`responses.jsonl`、`run.log` 和 `exit_code.txt`。explainer 不加载 Mbio adapter；不能把同一阶段的重试当作独立复现。

```powershell
python .\run_two_point_a100_20261029.py classifier --model-path <MODEL_PATH> --weights-manifest <WEIGHTS_MANIFEST> --adapter <MBIO_CHECKPOINT_100> --gpu <GPU_INDEX> --operator <OPERATOR_ID> --output .\a100_classifier_20261029
python .\run_two_point_a100_20261029.py explainer --model-path <MODEL_PATH> --weights-manifest <WEIGHTS_MANIFEST> --gpu <GPU_INDEX> --operator <OPERATOR_ID> --output .\a100_explainer_20261029
```

回收后只把上述两阶段的原始目录、环境/权重身份、日志、退出码和响应交回；先核对输入哈希和格式，再由陈明进核对模型选出的摘录定位。模型输出不能直接变成解释语义、分类或联合验收通过。
