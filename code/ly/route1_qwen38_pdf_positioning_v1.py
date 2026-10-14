#!/usr/bin/env python3
"""PDF sentence indexing and BM25 positioning for route1.

The index keeps the source PDF hash, 1-based page number, block/paragraph
number, sentence number, character offsets in the normalized page stream, and
a block bounding box.  It is intended for evidence verification after the
SciCiteVal/Sarol adapter returns evidence IDs; it does not alter labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover - exercised on the server
    raise SystemExit("PyMuPDF is required: pip install pymupdf") from exc

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - allows index-only use without BM25
    BM25Okapi = None

TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]", re.IGNORECASE)
SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+(?=[A-Z0-9\u4e00-\u9fff])")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    pieces = [part.strip() for part in SENTENCE_RE.split(text) if part.strip()]
    return [part for part in pieces if len(part) >= 10]


def build_index(pdf_path: Path) -> tuple[list[dict[str, Any]], str]:
    source_hash = sha256_file(pdf_path)
    rows: list[dict[str, Any]] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_idx, page in enumerate(doc, start=1):
            page_offset = 0
            block_no = 0
            blocks = page.get_text("blocks")
            for block in blocks:
                raw = str(block[4] or "")
                normalized = re.sub(r"\s+", " ", raw).strip()
                if not normalized:
                    continue
                block_no += 1
                block_start = page_offset
                page_offset += len(normalized) + 1
                sentences = split_sentences(normalized)
                local_offset = 0
                for sentence_no, sentence in enumerate(sentences):
                    local_start = normalized.find(sentence, local_offset)
                    if local_start < 0:
                        local_start = local_offset
                    local_end = local_start + len(sentence)
                    local_offset = local_end
                    rows.append({
                        "sentence_id": f"P{page_idx:03d}:B{block_no:03d}:S{sentence_no:03d}",
                        "text": sentence,
                        "page": page_idx,
                        "paragraph": block_no,
                        "sentence_idx": sentence_no,
                        "char_start": block_start + local_start,
                        "char_end": block_start + local_end,
                        "bbox": [round(float(x), 2) for x in block[:4]],
                        "source_file": pdf_path.name,
                        "source_sha256": source_hash,
                        "position_quality": "block_bbox",
                    })
    finally:
        doc.close()
    return rows, source_hash


def search(rows: list[dict[str, Any]], query: str, top_k: int) -> list[dict[str, Any]]:
    if BM25Okapi is None:
        raise SystemExit("rank_bm25 is required for search: pip install rank_bm25")
    if not rows:
        return []
    corpus = [tokenize(row["text"]) for row in rows]
    query_tokens = tokenize(query)
    scores = BM25Okapi(corpus).get_scores(query_tokens)
    order = sorted(range(len(rows)), key=lambda i: (-float(scores[i]), i))[:top_k]
    result = []
    for rank, idx in enumerate(order, start=1):
        item = dict(rows[idx])
        item["rank"] = rank
        item["score"] = round(float(scores[idx]), 6)
        result.append(item)
    return result


def write_index(rows: list[dict[str, Any]], pdf_path: Path, index_path: Path, source_hash: str) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    meta = {
        "task": "route1 PDF positioning index",
        "source_file": str(pdf_path),
        "source_sha256": source_hash,
        "num_sentences": len(rows),
        "index_sha256": sha256_file(index_path),
        "position_fields": ["page", "paragraph", "sentence_idx", "char_start", "char_end", "bbox"],
    }
    index_path.with_suffix(index_path.suffix + ".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_index(index_path: Path) -> list[dict[str, Any]]:
    with index_path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Index a PDF and position evidence with BM25")
    parser.add_argument("--pdf", type=Path, help="PDF to parse; required unless --index is used")
    parser.add_argument("--index", type=Path, help="Existing JSONL index to search")
    parser.add_argument("--save-index", type=Path, help="Write JSONL index and .meta.json")
    parser.add_argument("--query", help="One query/claim to search")
    parser.add_argument("--queries-jsonl", type=Path, help="JSONL with claim_id and query (or claim)")
    parser.add_argument("--output", type=Path, help="Output JSONL for --queries-jsonl")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    if args.top_k <= 0:
        raise SystemExit("--top-k must be positive")
    if args.pdf is None and args.index is None:
        raise SystemExit("Provide --pdf or --index")
    if args.pdf is not None and args.index is not None:
        raise SystemExit("Use --pdf or --index, not both")

    if args.pdf is not None:
        if not args.pdf.exists() or args.pdf.suffix.lower() != ".pdf":
            raise SystemExit(f"PDF does not exist or is not .pdf: {args.pdf}")
        rows, source_hash = build_index(args.pdf)
        if args.save_index:
            write_index(rows, args.pdf, args.save_index, source_hash)
        print(json.dumps({"pdf": str(args.pdf), "source_sha256": source_hash, "sentences": len(rows)}, ensure_ascii=False))
    else:
        rows = load_index(args.index)

    if args.query is not None:
        print(json.dumps({"query": args.query, "results": search(rows, args.query, args.top_k)}, ensure_ascii=False, indent=2))
    if args.queries_jsonl is not None:
        if args.output is None:
            raise SystemExit("--output is required with --queries-jsonl")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.queries_jsonl.open("r", encoding="utf-8") as source, args.output.open("w", encoding="utf-8", newline="\n") as target:
            for line_no, line in enumerate(source, 1):
                if not line.strip():
                    continue
                item = json.loads(line)
                query = item.get("query") or item.get("claim") or item.get("claim_text")
                if not query:
                    raise SystemExit(f"Missing query/claim at line {line_no}")
                target.write(json.dumps({
                    "claim_id": item.get("claim_id", line_no),
                    "query": query,
                    "results": search(rows, query, args.top_k),
                }, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(json.dumps({"output": str(args.output), "queries": sum(1 for line in args.queries_jsonl.open(encoding='utf-8') if line.strip())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
