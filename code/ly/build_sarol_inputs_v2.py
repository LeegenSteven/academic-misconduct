"""Rebuild frozen Sarol BM25 inputs without exposing tracking IDs to the model.

Standard library only. Gold is written separately and never passed to retrieval.
The four source hashes and the complete reconstructed v1 output hashes must match
the frozen v1 manifest before any v2 files are accepted.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re


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
LABELS = {"ACCURATE", "NOT_ACCURATE", "IRRELEVANT"}
TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?|[\u4e00-\u9fff]")
MARKER_RE = re.compile(r"<\|(?:multi_cit|cit|other_cit)\|>")
TRACKING_FIELD_RE = re.compile(r"\b(?:claim_id|sample_id|doc_id|source_doc_rank|sentence_id|gold|project_label)\s*[:=]", re.I)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(MARKER_RE.sub(" ", text or "").lower())


def bm25_rank(query: str, candidates: list[dict]) -> list[dict]:
    # Intentionally identical to the frozen v1 implementation (including ties).
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
    k1, b = 1.2, 0.75
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


def build_candidates(cited_doc_ids: list, corpus_by_id: dict[int, dict]) -> list[dict]:
    # Only cited_doc_ids are accepted: annotations cannot affect the candidate set.
    candidates = []
    for doc_index, raw_doc_id in enumerate(cited_doc_ids, start=1):
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
            candidates.append({
                "evidence_id": f"D{doc_index:02d}:S{sentence_index + 1:02d}",
                "doc_id": doc_id,
                "sentence_id": sentence_index,
                "source_doc_rank": doc_index,
                "text": text,
            })
    return candidates


def compact_evidence_ids(ranked: list[dict]) -> list[dict]:
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


def render_user_prompt(claim: str, evidence: list[dict]) -> str:
    lines = [f"引用论断：{claim}", "候选证据："]
    lines.extend(f"{item['evidence_id']} | {item['text']}" for item in evidence)
    lines.append("请按 schema 返回 JSON。")
    return "\n".join(lines)


def render_v1_user_prompt(claim_id: int, claim: str, evidence: list[dict]) -> str:
    lines = [f"claim_id: {claim_id}", f"引用论断：{claim}", "候选证据："]
    lines.extend(f"{item['evidence_id']} | doc_id={item['doc_id']} | {item['text']}" for item in evidence)
    lines.append("请按 schema 返回 JSON。")
    return "\n".join(lines)


def model_input_sha256(system: str, user: str) -> str:
    visible = {"system_prompt": system, "user_prompt": user}
    return hashlib.sha256(json.dumps(visible, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def jsonl_bytes(row: dict) -> bytes:
    return (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("wb") as stream:
        for row in rows:
            stream.write(jsonl_bytes(row))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=repo_root / "data/quality_v1/sarol")
    parser.add_argument("--v1-manifest", type=Path, default=repo_root / "results/route1_qwen38_v1/2026-10-13/sarol_bm25_top10_inputs_v1_2026-10-13/manifest_bm25_top10_sentences_v1.json")
    parser.add_argument("--output-dir", type=Path, default=repo_root / "results/route1_qwen38_v2/2026-10-15/sarol")
    args = parser.parse_args()
    frozen = json.loads(args.v1_manifest.read_text(encoding="utf-8"))
    prompt_hash = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    assert prompt_hash == frozen["system_prompt_sha256"], "System prompt changed"
    source_files = []
    for expected in frozen["source_files"]:
        filename = expected["path"].replace("\\", "/").rsplit("/", 1)[-1]
        source_path = args.source_dir / filename
        actual_hash = sha256(source_path)
        assert actual_hash == expected["sha256"], f"Frozen source SHA-256 mismatch: {filename}"
        assert source_path.stat().st_size == expected["bytes"], f"Frozen source size mismatch: {filename}"
        source_files.append({"path": f"data/quality_v1/sarol/{filename}", "sha256": actual_hash,
                             "bytes": source_path.stat().st_size, "matches_frozen_v1": True})

    corpus_rows = load_jsonl(args.source_dir / "corpus.jsonl")
    corpus_by_id = {int(row["doc_id"]): row for row in corpus_rows}
    assert len(corpus_by_id) == len(corpus_rows), "Duplicate corpus doc_id"
    manifest = {
        "manifest_version": "sarol_inputs_v2_2026-10-15",
        "source_revision": "88bf515d33dc484185174443a66f6dbf536850af",
        "source_files": source_files,
        "retriever": "Frozen v1 BM25 over all abstract sentence blocks in cited_doc_ids",
        "top_k": 10, "bm25_k1": 1.2, "bm25_b": 0.75,
        "ranking_tie_break": "score descending, then original candidate sentence order",
        "changes_from_v1": ["Remove claim_id line from model-visible user_prompt",
                            "Remove doc_id=... field from model-visible evidence lines",
                            "Keep original tracking IDs outside prompt; write labels/evidence only to gold sidecars"],
        "system_prompt_sha256": prompt_hash,
        "uses_gold_or_manual_evidence_for_retrieval": False,
        "split_policy": "Preserve quality_v1 train/dev/test membership and source order exactly",
        "evidence_id_policy": "Unchanged v1 compact Dxx:Sxx; external metadata retains original document/sentence positions",
        "input_sha256_definition": "sha256(UTF-8 json.dumps({system_prompt,user_prompt},ensure_ascii=False,sort_keys=True,separators=(',',':')))",
        "reasoning": "Must be explicitly disabled in actual training/inference chat-template settings",
        "gold_visibility": "Gold sidecars are for supervision/scoring; never concatenate them into user/system prompts",
        "corpus_audit": {"documents": len(corpus_rows),
                         "documents_with_empty_abstract_sentences": sum(isinstance(row.get("abstract"), list) and any(not str(text).strip() for text in row["abstract"]) for row in corpus_rows)},
        "generator": {"path": "code/ly/build_sarol_inputs_v2.py", "sha256": sha256(Path(__file__))},
        "v1_manifest": {"path": "results/route1_qwen38_v1/2026-10-13/sarol_bm25_top10_inputs_v1_2026-10-13/manifest_bm25_top10_sentences_v1.json",
                        "sha256": sha256(args.v1_manifest)},
        "splits": {},
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for split in ("train", "dev", "test"):
        claims = load_jsonl(args.source_dir / f"claims-{split}-model.jsonl")
        inputs, golds = [], []
        old_digest = hashlib.sha256()
        old_bytes = 0
        candidate_counts = Counter()
        label_counts = Counter()
        alignment_counts = Counter()
        missing_gold_evidence = 0
        all_candidate_count = 0
        missing_doc_claim_ids = []
        for claim in claims:
            claim_id = int(claim["id"])
            label = claim["gold"]
            assert label in LABELS, f"Unknown label: {split}/{claim_id}"
            assert claim.get("training_label_ready") is True, f"Unready source label: {split}/{claim_id}"
            # Annotation-bearing claim object is deliberately not passed to retrieval.
            all_candidates = build_candidates(claim.get("cited_doc_ids") or [], corpus_by_id)
            ranked = compact_evidence_ids(bm25_rank(claim.get("claim", ""), all_candidates)[:10])
            allowed = [item["evidence_id"] for item in ranked]
            all_candidate_count += len(all_candidates)
            candidate_counts[len(ranked)] += 1
            label_counts[label] += 1
            alignment_counts[str(claim.get("annotation_alignment_status"))] += 1
            missing_gold_evidence += claim.get("evidence_missing") is True
            if not all_candidates:
                missing_doc_claim_ids.append(claim_id)
            old_row = {
                "claim_id": claim_id, "system_prompt": SYSTEM_PROMPT,
                "user_prompt": render_v1_user_prompt(claim_id, claim["claim"], ranked),
                "allowed_evidence_ids": allowed, "candidate_evidence": ranked,
                "input_warning": "no_candidate_evidence" if not ranked else None,
            }
            old_line = jsonl_bytes(old_row)
            old_digest.update(old_line)
            old_bytes += len(old_line)
            user = render_user_prompt(claim["claim"], ranked)
            assert not TRACKING_FIELD_RE.search(user), f"Tracking/annotation field in prompt: {split}/{claim_id}"
            assert len(allowed) == len(set(allowed))
            assert all(re.fullmatch(r"D\d{2}:S\d{2}", value) for value in allowed)
            inputs.append({
                "claim_id": claim_id, "system_prompt": SYSTEM_PROMPT, "user_prompt": user,
                "candidate_evidence": ranked, "allowed_evidence_ids": allowed,
                "input_sha256": model_input_sha256(SYSTEM_PROMPT, user),
            })
            golds.append({
                "claim_id": claim_id, "label": label,
                "gold_evidence": claim.get("evidence", {}),
                "evidence_missing": claim.get("evidence_missing"),
                "annotation_alignment_status": claim.get("annotation_alignment_status"),
                "training_label_ready": claim.get("training_label_ready"),
                "source_sample_id": claim.get("sample_id"),
            })
        assert old_digest.hexdigest() == frozen["outputs"][split]["sha256"], f"v1 reconstruction mismatch: {split}"
        assert old_bytes == frozen["outputs"][split]["bytes"], f"v1 reconstructed size mismatch: {split}"
        assert len(inputs) == frozen["splits"][split]["claims"]
        assert all_candidate_count == frozen["splits"][split]["candidate_sentence_blocks_before_top10"]
        assert dict(sorted((str(k), v) for k, v in candidate_counts.items())) == frozen["splits"][split]["candidate_sentence_count_distribution"]
        assert len({row["claim_id"] for row in inputs}) == len(inputs)
        assert [row["claim_id"] for row in inputs] == [row["claim_id"] for row in golds]
        assert [row["claim_id"] for row in inputs] == [int(row["id"]) for row in claims]
        outputs = {}
        for kind, rows in (("inputs", inputs), ("gold", golds)):
            path = args.output_dir / f"{split}.{kind}.jsonl"
            write_jsonl(path, rows)
            reread = load_jsonl(path)
            assert reread == rows
            outputs[kind] = {"path": f"results/route1_qwen38_v2/2026-10-15/sarol/{path.name}",
                             "sha256": sha256(path), "bytes": path.stat().st_size, "records": len(rows)}
        manifest["splits"][split] = {
            "records": len(inputs), "unique_claim_ids": len({row["claim_id"] for row in inputs}),
            "label_distribution": dict(sorted(label_counts.items())),
            "source_annotation_alignment_status_distribution": dict(sorted(alignment_counts.items())),
            "source_evidence_missing_records": missing_gold_evidence,
            "candidate_sentence_blocks_before_top10": all_candidate_count,
            "candidate_sentence_count_distribution": dict(sorted((str(k), v) for k, v in candidate_counts.items())),
            "missing_candidate_claim_ids": missing_doc_claim_ids,
            "input_gold_ids_and_order_match": True,
            "source_order_and_membership_preserved": True,
            "v1_reconstructed_lf_sha256": old_digest.hexdigest(),
            "v1_reconstructed_bytes": old_bytes,
            "v1_complete_output_byte_hash_matches": True,
            "candidate_text_ids_metadata_and_order_unchanged_from_v1": True,
            "tracking_annotation_field_prefixes_in_model_prompt": 0,
            "outputs": outputs,
        }
        print(json.dumps({"split": split, "records": len(inputs), "v1_exact_reconstruction": True,
                          "label_distribution": dict(sorted(label_counts.items())),
                          "input_sha256": outputs["inputs"]["sha256"]}, ensure_ascii=False), flush=True)
    manifest["validation"] = {
        "all_source_hashes_match_frozen_v1": True,
        "all_v1_outputs_reconstructed_byte_identically": True,
        "gold_and_model_inputs_written_to_separate_files": True,
        "all_input_gold_ids_and_order_match": True,
        "all_selected_candidate_ids_are_valid_unique_Dxx_Sxx": True,
        "system_prompt_unchanged_from_v1": True,
        "model_inference_or_test_tuning_performed": False,
        "retrieval_annotation_independence": "build_candidates accepts only cited_doc_ids and corpus; bm25_rank accepts only raw claim text and candidates",
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"manifest": "results/route1_qwen38_v2/2026-10-15/sarol/manifest.json", "status": "all_checks_passed"}), flush=True)


if __name__ == "__main__":
    main()
