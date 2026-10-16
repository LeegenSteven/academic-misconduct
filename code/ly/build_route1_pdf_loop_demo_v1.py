#!/usr/bin/env python3
"""Prepare one traceable two-PDF citation demo, separate from frozen v2 data.

The citing paper is SciCiteVal (LREC 2026); its Wadden et al. (2020)
reference points to the SciFact paper. The output is an inference input and a
manually reviewed reference label, not a model prediction or benchmark score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import fitz

from route1_qwen38_pdf_positioning_v1 import build_index, search, sha256_file

CLAIM_START = "Wadden et al. (2020)"
CLAIM_END = "Subsequent work"
EVIDENCE_ID = "D01:S01"
DEMO_ID = "pdf_demo_sciciteval_scifact_001"


def normalize_pdf_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"(?<=[A-Za-z])-\s+(?=[A-Za-z])", "", value)
    return re.sub(r"\s+", " ", value).strip()


def rects(page: fitz.Page, phrase: str) -> list[list[float]]:
    return [[round(float(v), 2) for v in rect] for rect in page.search_for(phrase)]


def one_rect(page: fitz.Page, phrase: str) -> list[float]:
    found = rects(page, phrase)
    if len(found) != 1:
        raise ValueError(f"Expected one PDF match for {phrase!r}, found {len(found)}")
    return found[0]


def find_citation(citing: fitz.Document) -> tuple[str, dict, dict]:
    matches = []
    for page_no, page in enumerate(citing, 1):
        for block in page.get_text("blocks"):
            if CLAIM_START in str(block[4]):
                matches.append((page_no, page, block))
    if len(matches) != 1:
        raise ValueError(f"Expected one citing paragraph, found {len(matches)}")
    page_no, page, block = matches[0]
    context = normalize_pdf_text(str(block[4]))
    claim_match = re.search(re.escape(CLAIM_START) + r".*?(?=" + re.escape(CLAIM_END) + r")", context)
    if not claim_match:
        raise ValueError("Could not isolate the SciFact citation claim")
    claim = claim_match.group().strip()
    citation = {
        "page": page_no,
        "citation_marker": CLAIM_START,
        "marker_bbox": one_rect(page, CLAIM_START),
        "context_block_bbox": [round(float(v), 2) for v in block[:4]],
        "position_quality": "marker_bbox_and_context_block_bbox",
    }
    references = []
    for ref_page_no, ref_page in enumerate(citing, 1):
        author = rects(ref_page, "David Wadden")
        title = rects(ref_page, "Fact or fiction")
        if len(author) == 1 and len(title) == 1:
            references.append({"page": ref_page_no, "author_bbox": author[0], "title_bbox": title[0]})
    if len(references) != 1:
        raise ValueError(f"Expected one matching reference entry, found {len(references)}")
    return claim, citation, references[0]


def write_jsonl(path: Path, item: dict) -> str:
    raw = (json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--citing-pdf", type=Path, required=True)
    parser.add_argument("--cited-pdf", type=Path, required=True)
    parser.add_argument("--prompt-reference", type=Path, default=Path("results/route1_qwen38_v2/2026-10-15/sciciteval/dev.inputs.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/route1_qwen38_v2/2026-10-16/pdf_demo_sciciteval_scifact"))
    args = parser.parse_args()
    for path in (args.citing_pdf, args.cited_pdf, args.prompt_reference):
        if not path.is_file():
            parser.error(f"Missing input: {path}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    citing = fitz.open(args.citing_pdf)
    cited = fitz.open(args.cited_pdf)
    try:
        claim, citation_point, reference_entry = find_citation(citing)
        cited_title = normalize_pdf_text(cited[0].get_text())
        if "Fact or Fiction: Verifying Scientific Claims" not in cited_title:
            raise ValueError("Cited PDF title does not match the citing reference")
    finally:
        citing.close()
        cited.close()

    rows, cited_hash = build_index(args.cited_pdf)
    ranked = search(rows, claim, 5)
    best = ranked[0]
    if best["page"] != 1 or "1.4K" not in best["text"] or best["sentence_idx"] < 1:
        raise ValueError("Top cited evidence is not the expected SciFact abstract sentence")
    preceding = next((row for row in rows if row["page"] == best["page"]
                      and row["paragraph"] == best["paragraph"]
                      and row["sentence_idx"] == best["sentence_idx"] - 1), None)
    if preceding is None or "REFUTES" not in preceding["text"]:
        raise ValueError("Could not verify the preceding SUPPORTS/REFUTES abstract sentence")
    evidence = normalize_pdf_text(preceding["text"] + " " + best["text"])

    with args.prompt_reference.open(encoding="utf-8") as handle:
        system_prompt = json.loads(next(line for line in handle if line.strip()))["system_prompt"]
    user_prompt = f"施引上下文：{claim}\n被引内容：\n{EVIDENCE_ID} | {evidence}\n请只输出符合要求的 JSON。"
    prompt_payload = {"system_prompt": system_prompt, "user_prompt": user_prompt}
    prompt_sha = hashlib.sha256(json.dumps(prompt_payload, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":")).encode("utf-8")).hexdigest()
    model_input = {
        "claim_id": DEMO_ID,
        **prompt_payload,
        "allowed_evidence_ids": [EVIDENCE_ID],
        "candidate_evidence": [{"evidence_id": EVIDENCE_ID, "text": evidence,
                                "locator": f"pdf:p{best['page']}:{preceding['sentence_id']}+{best['sentence_id']}"}],
        "input_warning": "Ad hoc two-PDF demonstration; not in frozen v2 Train/Dev/Test.",
        "input_sha256": prompt_sha,
    }
    reference_gold = {"claim_id": DEMO_ID, "label": "ACCURATE"}
    input_sha = write_jsonl(args.output_dir / "demo.inputs.jsonl", model_input)
    gold_sha = write_jsonl(args.output_dir / "demo.reference_gold.jsonl", reference_gold)
    manifest = {
        "status": "prepared_no_model_run",
        "scope": "manual two-PDF demonstration outside frozen v2 splits",
        "claim_id": DEMO_ID,
        "citing_pdf": {"file": args.citing_pdf.name, "sha256": sha256_file(args.citing_pdf)},
        "cited_pdf": {"file": args.cited_pdf.name, "sha256": cited_hash},
        "citation_point": citation_point,
        "reference_entry": reference_entry,
        "claim_text": claim,
        "retrieval": {"method": "BM25 over cited-PDF sentence index", "top_sentence_id": best["sentence_id"],
                      "top_rank": best["rank"], "top_score": best["score"], "index_sentences": len(rows)},
        "cited_evidence": {"page": best["page"], "sentence_ids": [preceding["sentence_id"], best["sentence_id"]],
                           "block_bbox": best["bbox"], "position_quality": "block_bbox", "text": evidence},
        "human_reference": {"label": "ACCURATE", "status": "manual_demo_review_not_dataset_gold",
                            "reason": "被引论文摘要直接说明约 1.4K 条专家撰写的科学论断、摘要证据、SUPPORTS/REFUTES 标签和理由，与施引论断一致。"},
        "prompt_contract": "Frozen SciCiteVal v2 system prompt and D01:S01 user-prompt format; only these prompts go to the model",
        "prompt_sha256": prompt_sha,
        "files": {"demo.inputs.jsonl": input_sha, "demo.reference_gold.jsonl": gold_sha},
    }
    (args.output_dir / "citation_loop.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"status": manifest["status"], "citation_page": citation_point["page"],
                      "evidence_page": best["page"], "retrieval_rank": best["rank"],
                      "output_dir": str(args.output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
