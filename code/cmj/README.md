# cmj — 陈明进

个人工作区，另一人一般不修改本目录。代码与数据快照分开保存，避免把本机路径或原始下载包带入仓库。

## 研究内容

路线一（Sarol 2024）引用内容合理性语义识别。主线工作：原始标签到项目三分类的映射、BM25/MonoT5 检索对照、在 Sarol 自家训练集上微调 MultiVerS、证据定位人工核对、训练集内难样本过采样验证，以及开源候选数据源核查。

## 入口（按执行顺序）

| 脚本 | 用途 |
|---|---|
| `convert_three_class_v2.py` | 原始 Sarol 标签转换为项目三分类 v2（Train/Dev/Test） |
| `recompute_metrics_v2.py` | 在 v2 数据上重算三分类指标 |
| `run_task2_three_inputs.py` | 三种证据输入（金标准 / BM25 / 无句）对照 |
| `run_task3_six_retrieval.py` | BM25 与 MonoT5 六档检索对比 |
| `run_task4_finetune.py` | 在 2,141 条 Train 上微调 MultiVerS（step2141 主权重） |
| `run_task4_eval_dev.py` / `run_task4_eval_test.py` | 在 Dev / Test 上评测微调模型 |
| `gen_task2_checklist.py` | 生成证据定位 60 条人工核对表 |
| `run_task3_train_selfeval.py` | 用 step2141 在 Train 上自评，挖出判错与低置信歪曲样本 |
| `run_task3_oversample2x.py` | 将难样本 2 倍重复加入训练集重训（验证为无效） |
| `run_bm25_*.py` / `run_monot5_*.py` / `run_multivers_*.py` | 早期检索与 MultiVerS 探索脚本 |

多数历史脚本支持命令行路径参数；若没有显式传入路径，不要假设仓库中存在本机历史目录。运行前先用 `python <script> --help` 查看参数。

## 读写的数据

- 输入：`data/interim/converted-three-class-v2/claims-{train,dev,test}.jsonl`；`data/raw/` 下 Sarol 文献语料 `corpus.jsonl`
- 输出：`results/cmj/<任务>/...`（评测 json、预测 jsonl、过采样 manifest、证据定位核对表）

## 关键结果

- Test 606 条（step2141，已冻结，只评一次）：方案 B 准确率 0.6040（334/553），全量 0.5512（334/606），Macro-F1 0.3642；歪曲类召回 0.5482；IRRELEVANT 52 条全部判错。
- 证据定位 60 条人工核对：有效率 0.60（36/60）。
- 难样本过采样 2 倍：550 条难样本，2141→2691 条重训，Dev 方案 B 准确率 0.6507→0.346，316 条全判歪曲类，结论为补样无效。

## 备注

- 环境：Python 3.9.25、PyTorch 2.8.0（CPU）、transformers 4.57.1；编码器为 Longformer-large-4096。
- 模型权重（.pt，单个约 1.7GB）不进 Git，权重 SHA-256 与获取方式见 `docs/cmj/` 及数据层 README。
- 推理可复现（权重已冻结）；训练因随机种子未固定，完全复现受限，后续训练固定 seed=42。
- 数据源下载、需挂代理的资源入口见 `scripts/`。
