# 修复后的训练数据

两位同学本次模型训练读取 [sarol/](sarol/) 中三份 `*-model.jsonl` 和 `corpus.jsonl`。Train2141、Dev316、Test606，分类标签读显式 `gold`。

已修正39条旧版标签错配（Train36、Test3），官方划分保持不变。取用路径、现有代码调整及验证方式见 [训练数据使用说明](TRAINING_GUIDE.md)。
