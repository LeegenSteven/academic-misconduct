# Sarol三分类修复版（sarol-quality-v1）

主实验文件：claims-train-model.jsonl、claims-dev-model.jsonl、claims-test-model.jsonl及corpus.jsonl。数量为2141/316/606。金标准类别读gold，无金证据由evidence_missing记录。

39条标签错配已按固定官方版本的原始标注更正；Test类别为386ACCURATE、170NOT_ACCURATE、50IRRELEVANT。官方划分保留。

使用方式见 [训练说明](../TRAINING_GUIDE.md)。字节哈希与来源在training_manifest.json，原始上游版权声明在UPSTREAM_LICENSE.txt。
