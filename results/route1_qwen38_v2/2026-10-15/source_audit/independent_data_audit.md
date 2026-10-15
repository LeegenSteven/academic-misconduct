# 独立数据审计（只读）

上游：88bf515d33dc484185174443a66f6dbf536850af。未修改 repo。

SciCiteVal 原始 TSV 与冻结哈希一致：True；1034 行 row_id 覆盖完整且无重复，标签映射无差异。当前分组为 {'train': 713, 'test': 257, 'dev': 54, 'excluded_conflict': 10}。group_key、source_paper_id、完全相同上下文/被引内容/二者组合均无跨 active split，可保持原分组。

原始 row_id 可由阈值及奇偶规则预测 1034/1034 个标签，Dev54 全部提示词仍包含 claim_id。应在所有分组中统一移除。

Sarol 四个本地源文件的字节数及 SHA-256 与冻结 BM25 manifest 均一致：True，可直接使用本地修复包。

Sarol claims-*-model.jsonl 实际含 gold/evidence 字段，但当前 BM25 仅使用 id/claim/cited_doc_ids。新生成器应白名单取字段，不得整行序列化。ID 在不同 split 间重叠，外部映射必须同时带数据集和 split。既有审计记录 5 个 citing_pmcid、1 个 strict_claim_text 跨官方划分；保留官方协议时要保留这一说明。

修复与验收：

- Keep SciCiteVal 713/54/257 membership and isolate 10 conflicts; do not change labels.
- Remove original IDs from model-visible prompts; retain external dataset/split/claim_id mapping.
- Use one generator per dataset for Train/Dev/Test. SciCiteVal D01:S01 keeps supplied passage; Sarol BM25 top-10 sentences is retained.
- Model message allowlist contains only system_prompt/user_prompt. Sarol source objects contain gold/evidence and must never be serialized wholesale.
- Validate exact input/gold ID and order coverage, evidence ID uniqueness and mapping, and actual byte hashes after LF serialization.
- Train labels enter assistant targets only. Preserve loss masks through collator; reject missing/extra/duplicate IDs instead of silent skips.
- Reject truncation of assistant targets; report input lengths and apply a shared documented policy if evidence truncation is necessary.
- INVALID predictions are incorrect and must count toward per-class false negatives; use full-label parsing, never ACCURATE substring matching.
- Retain Sarol official split but disclose inherited citing-paper/text overlap; do not claim paper-disjoint evaluation.
