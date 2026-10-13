from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path


SYSTEM_PROMPT = (
    "你是学术引文核验助手。只依据给出的候选证据判断引用论断，不使用外部知识。\n"
    "标签定义：\n"
    "ACCURATE：候选证据直接支持论断的实质内容，且没有重要歪曲。\n"
    "NOT_ACCURATE：候选证据与论断矛盾，或论断存在重要的未获支持、错误转述、过度简化或归属错误。\n"
    "IRRELEVANT：候选证据与论断没有实质关联，无法用于支持或反驳。\n"
    "必须输出一个 JSON 对象，不要输出 Markdown。evidence_ids 只能从给出的候选证据编号中选择，最多 5 个；"
    "reason 使用中文且不超过 120 个汉字；confidence 为 0 到 1 的小数。\n"
    "严格要求：evidence_ids 只能使用候选证据左侧完整编号，格式必须是 D01:S01，不能写成 D01、D1 或文档编号；"
    "如果没有可用证据就返回空数组。"
)

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?|[\u4e00-\u9fff]")
MARKER_RE = re.compile(r"<\|(?:multi_cit|cit|other_cit)\|>")


def tokens(text: str) -> list[str]:
    text = MARKER_RE.sub(" ", text or "").lower()
    return TOKEN_RE.findall(text)


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def render_user_prompt(claim_id: int, claim: str, evidence: list[dict]) -> str:
    lines = [f"claim_id: {claim_id}", f"引用论断：{claim}", "候选证据："]
    for item in evidence:
        lines.append(f"{item['evidence_id']} | doc_id={item['doc_id']} | {item['text']}")
    lines.append("请按 schema 返回 JSON。")
    return "\n".join(lines)


def bm25_rank(query: str, candidates: list[dict]) -> list[dict]:
    """Rank candidate sentence blocks for one claim with deterministic BM25."""
    if not candidates:
        return []
    query_terms = Counter(tokens(query))
    docs = [tokens(item["text"]) for item in candidates]
    n_docs = len(docs)
    lengths = [len(doc) for doc in docs]
    avgdl = sum(lengths) / n_docs if n_docs else 1.0
    document_frequency = Counter()
    for doc in docs:
        document_frequency.update(set(doc))
    k1 = 1.2
    b = 0.75
    scored = []
    for index, doc in enumerate(docs):
        term_frequency = Counter(doc)
        length = lengths[index]
        score = 0.0
        for term, qtf in query_terms.items():
            df = document_frequency.get(term, 0)
            if not df:
                continue
            idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
            tf = term_frequency.get(term, 0)
            if not tf:
                continue
            denominator = tf + k1 * (1.0 - b + b * length / avgdl)
            score += idf * (tf * (k1 + 1.0) / denominator) * qtf
        scored.append((score, index, candidates[index]))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored]


def build_candidates(claim: dict, corpus_by_id: dict[int, dict]) -> list[dict]:
    candidates = []
    for doc_index, raw_doc_id in enumerate(claim.get("cited_doc_ids") or [], start=1):
        doc_id = int(raw_doc_id)
        doc = corpus_by_id.get(doc_id)
        if not doc:
            continue
        abstract = doc.get("abstract") or []
        if not isinstance(abstract, list):
            abstract = [str(abstract)]
        sentences = [str(text).strip() for text in abstract if str(text).strip()]
        if not sentences and str(doc.get("title") or "").strip():
            sentences = [str(doc["title"]).strip()]
        for sentence_index, text in enumerate(sentences):
            candidates.append(
                {
                    "evidence_id": f"D{doc_index:02d}:S{sentence_index + 1:02d}",
                    "doc_id": doc_id,
                    "sentence_id": sentence_index,
                    "source_doc_rank": doc_index,
                    "text": text,
                }
            )
    return candidates


def compact_evidence_ids(ranked: list[dict]) -> list[dict]:
    """Use two-digit IDs for selected evidence while retaining source positions."""
    doc_slots: dict[int, int] = {}
    sentence_slots: Counter[int] = Counter()
    compacted = []
    for item in ranked:
        doc_id = int(item["doc_id"])
        if doc_id not in doc_slots:
            doc_slots[doc_id] = len(doc_slots) + 1
        sentence_slots[doc_id] += 1
        new_item = dict(item)
        new_item["evidence_id"] = f"D{doc_slots[doc_id]:02d}:S{sentence_slots[doc_id]:02d}"
        compacted.append(new_item)
    return compacted


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    corpus_rows = load_jsonl(args.data_dir / "corpus.jsonl")
    corpus_by_id = {int(row["doc_id"]): row for row in corpus_rows}
    split_files = {
        "train": "claims-train-model.jsonl",
        "dev": "claims-dev-model.jsonl",
        "test": "claims-test-model.jsonl",
    }
    manifest = {
        "manifest_version": "sarol_bm25_top10_sentence_inputs_v1",
        "retriever": "BM25 over all abstract sentence blocks in cited_doc_ids",
        "top_k": 10,
        "evidence_id_policy": "compact selected-document slots and selected-sentence slots to D01:S01 format; retain doc_id, source_doc_rank and source sentence_id",
        "uses_gold_or_manual_evidence": False,
        "reasoning": "off is a server/request inference setting; it is not encoded in the input file",
        "source_files": [],
        "outputs": {},
        "splits": {},
    }
    corpus_path = args.data_dir / "corpus.jsonl"
    manifest["source_files"].append(
        {"path": str(corpus_path), "sha256": sha256(corpus_path), "bytes": corpus_path.stat().st_size}
    )

    for split, filename in split_files.items():
        claims_path = args.data_dir / filename
        claims = load_jsonl(claims_path)
        manifest["source_files"].append(
            {"path": str(claims_path), "sha256": sha256(claims_path), "bytes": claims_path.stat().st_size}
        )
        output_path = args.output_dir / f"model_inputs_{split}_bm25_top10_sentences.jsonl"
        rows = []
        total_before = 0
        candidate_counts = Counter()
        missing_doc_claims = []
        for claim in claims:
            all_candidates = build_candidates(claim, corpus_by_id)
            total_before += len(all_candidates)
            ranked = compact_evidence_ids(bm25_rank(claim.get("claim", ""), all_candidates)[:10])
            candidate_counts[len(ranked)] += 1
            if not all_candidates:
                missing_doc_claims.append(int(claim["id"]))
            rows.append(
                {
                    "claim_id": int(claim["id"]),
                    "system_prompt": SYSTEM_PROMPT,
                    "user_prompt": render_user_prompt(int(claim["id"]), claim["claim"], ranked),
                    "allowed_evidence_ids": [item["evidence_id"] for item in ranked],
                    "candidate_evidence": ranked,
                    "input_warning": "no_candidate_evidence" if not ranked else None,
                }
            )
        with output_path.open("w", encoding="utf-8", newline="") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        manifest["outputs"][split] = {
            "path": str(output_path),
            "sha256": sha256(output_path),
            "bytes": output_path.stat().st_size,
        }
        manifest["splits"][split] = {
            "claims": len(rows),
            "candidate_sentence_blocks_before_top10": total_before,
            "candidate_sentence_count_distribution": {str(k): v for k, v in sorted(candidate_counts.items())},
            "missing_candidate_claim_ids": missing_doc_claims,
            "unique_claim_ids": len({row["claim_id"] for row in rows}),
        }
        print(json.dumps({"split": split, "claims": len(rows), "output": str(output_path), "distribution": dict(candidate_counts)}, ensure_ascii=False))

    manifest_path = args.output_dir / "manifest_bm25_top10_sentences_v1.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "corpus_blocks": len(corpus_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
