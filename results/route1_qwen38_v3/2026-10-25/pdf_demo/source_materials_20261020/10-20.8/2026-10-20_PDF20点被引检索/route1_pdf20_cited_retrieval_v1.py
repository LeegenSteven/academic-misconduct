# -*- coding: utf-8 -*-
"""路线一 PDF20点 被引端批量BM25检索脚本 v1.

输入：李云交接包 cited_retrieval_requests.jsonl + pdf_text/<sha256>/blocks.jsonl
输出：cited_evidence_results.jsonl，每点含 top-k 候选证据（ID/原文/页序/字符区间/bbox/分数）
      + retrieval_manifest.json（检索配置、统计、失败记录）

检索参数（v3，固定后不再改）：
  - 分词：小写化 + 非字母数字分隔，保留长度>=2的token
  - BM25：k1=1.2, b=0.75
  - top_k=10
  - 检索范围：仅指定被引PDF全文blocks
  - 证据ID格式：E01..E10（按BM25分数降序）
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

from rank_bm25 import BM25Okapi

BASE = Path(r"C:\Users\Administrator\AppData\Local\Temp\ly_pdf20_20261020")
REQ_PATH = BASE / "cited_retrieval_requests.jsonl"
PDF_TEXT_DIR = BASE / "pdf_text"
OUT_DIR = Path(r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_PDF20点被引检索")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSONL = OUT_DIR / "cited_evidence_results.jsonl"
OUT_MANIFEST = OUT_DIR / "retrieval_manifest.json"

TOP_K = 10
BM25_K1 = 1.2
BM25_B = 0.75
TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """小写化 + 字母数字分词，保留长度>=2的token。"""
    return [t for t in TOKEN_RE.findall(text.lower()) if len(t) >= 2]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


MIN_BLOCK_CHARS = 50  # 过滤过短block（页眉页脚等）
# 参考文献条目模式：作者名缩写 + et al. + 年份，如 "Li,J.W. et al. (2013)" 或 "Bolger,A.M. et al."
REF_PATTERN = re.compile(
    r"^[A-Z][a-zA-Z'-]+(?:,\s*[A-Z]\.?)+(?:\s+et\s+al\.)?\s*\(\d{4}\)"
    r"|^[A-Z][a-zA-Z'-]+,\s*[A-Z]\.\s*(?:[A-Z]\.\s*)*et\s+al\."
)
LOW_CONFIDENCE_SCORE = 15.0  # top1分数低于此值标注为低置信度


def is_reference_block(text: str) -> bool:
    """判断block是否为参考文献条目。

    启发式：以作者名缩写模式开头，或包含'et al.'且长度<400字符且位于论文后半部分。
    """
    t = text.strip()
    if len(t) < 50:
        return True
    # 模式1：以 "Author, A.B. et al. (Year)" 开头
    if REF_PATTERN.match(t):
        return True
    # 模式2：短block（<400字符）包含 et al. + 年份，且不以大写句子开头
    if len(t) < 400 and "et al." in t and re.search(r"\b(19|20)\d{2}\b", t):
        # 检查是否以句子开头（大写字母+普通单词），参考文献通常以作者名开头
        first_word = t.split()[0] if t.split() else ""
        if "," in first_word or first_word.endswith("."):
            return True
    return False


def load_blocks(pdf_sha256: str) -> tuple[list[dict], int, int]:
    """加载指定被引PDF的blocks.jsonl，过滤过短block和参考文献条目。

    返回 (有效blocks, 过短过滤数, 参考文献过滤数)。
    """
    blocks_path = PDF_TEXT_DIR / pdf_sha256 / "blocks.jsonl"
    if not blocks_path.exists():
        return [], 0, 0
    all_blocks = []
    with blocks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_blocks.append(json.loads(line))
    num_short = 0
    num_ref = 0
    filtered = []
    for b in all_blocks:
        raw = b.get("raw_text", "").strip()
        if len(raw) < MIN_BLOCK_CHARS:
            num_short += 1
            continue
        if is_reference_block(raw):
            num_ref += 1
            continue
        filtered.append(b)
    return filtered, num_short, num_ref


def build_bm25(blocks: list[dict]) -> BM25Okapi:
    """用block的raw_text构建BM25索引。"""
    corpus = [tokenize(b.get("raw_text", "")) for b in blocks]
    return BM25Okapi(corpus, k1=BM25_K1, b=BM25_B)


def retrieve_case(req: dict) -> dict:
    """对单个引用点执行检索，返回结果记录。"""
    case_id = req["case_id"]
    cited = req["cited_pdf"]
    pdf_sha256 = cited["sha256"]
    pmcid = cited["pmcid"]
    title = cited["title"]

    query = req.get("target_claim_scope_proposal", "").strip()
    citing_context = req.get("citing_context_marked", "")

    result = {
        "case_id": case_id,
        "pair_id": req.get("pair_id"),
        "target_reference_id": req.get("target_reference_id"),
        "cited_pmcid": pmcid,
        "cited_title": title,
        "cited_pdf_sha256": pdf_sha256,
        "cited_pdf_relative_path": cited.get("relative_path"),
        "query": query,
        "query_source": "target_claim_scope_proposal",
        "retrieval_scope": req.get("retrieval_scope", "this cited PDF only"),
        "bm25_k1": BM25_K1,
        "bm25_b": BM25_B,
        "top_k": TOP_K,
        "tokenizer": "lowercase + [a-z0-9]+, len>=2",
        "candidates": [],
        "status": "ok",
        "note": "",
    }

    if not query:
        result["status"] = "no_query"
        result["note"] = "target_claim_scope_proposal为空，无法检索"
        return result

    blocks, num_short, num_ref = load_blocks(pdf_sha256)
    if not blocks:
        result["status"] = "no_blocks"
        result["note"] = "未找到有效blocks（全部被过滤或文件不存在）"
        return result

    result["total_blocks"] = len(blocks)
    result["blocks_filtered_short"] = num_short
    result["blocks_filtered_reference"] = num_ref

    bm25 = build_bm25(blocks)
    query_tokens = tokenize(query)
    scores = bm25.get_scores(query_tokens)

    # 按分数降序取top_k
    ranked = sorted(range(len(blocks)), key=lambda i: scores[i], reverse=True)[:TOP_K]

    for rank, idx in enumerate(ranked, 1):
        b = blocks[idx]
        score = float(scores[idx])
        evidence_id = f"E{rank:02d}"
        candidate = {
            "evidence_id": evidence_id,
            "rank": rank,
            "bm25_score": round(score, 6),
            "pdf_page": b.get("pdf_page"),
            "block_number": b.get("block_number"),
            "char_start": b.get("char_start"),
            "char_end_exclusive": b.get("char_end_exclusive"),
            "bbox": b.get("bbox"),
            "raw_text": b.get("raw_text", ""),
            "raw_text_sha256": b.get("raw_text_sha256"),
            "granularity": "pdf_text_block",
        }
        result["candidates"].append(candidate)

    result["num_candidates_returned"] = len(result["candidates"])
    # 检查最高分是否为0（无匹配）
    if result["candidates"] and result["candidates"][0]["bm25_score"] == 0.0:
        result["note"] = "top1 BM25分数为0，query与被引全文无token重叠，需人工核查"
        result["status"] = "zero_score_top1"
    elif result["candidates"] and result["candidates"][0]["bm25_score"] < LOW_CONFIDENCE_SCORE:
        result["note"] = (
            f"top1 BM25分数({result['candidates'][0]['bm25_score']:.2f})低于阈值"
            f"{LOW_CONFIDENCE_SCORE}，query可能在被引全文中无直接对应，需人工核查"
        )
        result["status"] = "low_confidence"

    return result


def main():
    print(f"读取检索请求: {REQ_PATH}")
    with REQ_PATH.open("r", encoding="utf-8") as f:
        reqs = [json.loads(line) for line in f if line.strip()]
    print(f"共 {len(reqs)} 个引用点")

    results = []
    stats = {"total": len(reqs), "ok": 0, "low_confidence": 0, "zero_score_top1": 0, "no_query": 0, "no_blocks": 0}

    for i, req in enumerate(reqs, 1):
        print(f"[{i}/{len(reqs)}] {req['case_id']} -> {req['cited_pdf']['pmcid']}")
        r = retrieve_case(req)
        results.append(r)
        stats[r["status"]] = stats.get(r["status"], 0) + 1
        print(f"    status={r['status']}, candidates={r.get('num_candidates_returned', 0)}, "
              f"top1_score={r['candidates'][0]['bm25_score'] if r['candidates'] else 'N/A'}")

    # 写结果
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n结果写入: {OUT_JSONL}")

    # 写manifest
    manifest = {
        "batch": "路线一PDF20点被引端检索 v1",
        "date": "2026-10-20",
        "input_requests": str(REQ_PATH),
        "input_pdf_text_dir": str(PDF_TEXT_DIR),
        "output_results": str(OUT_JSONL),
        "retrieval_config": {
            "engine": "rank_bm25.BM25Okapi",
            "k1": BM25_K1,
            "b": BM25_B,
            "top_k": TOP_K,
            "tokenizer": "lowercase + regex [a-z0-9]+, min token length 2",
            "min_block_chars": MIN_BLOCK_CHARS,
            "scope": "per-case cited PDF blocks only",
            "query_field": "target_claim_scope_proposal",
        },
        "stats": stats,
        "case_summary": [
            {
                "case_id": r["case_id"],
                "cited_pmcid": r["cited_pmcid"],
                "status": r["status"],
                "num_candidates": r.get("num_candidates_returned", 0),
                "top1_score": r["candidates"][0]["bm25_score"] if r["candidates"] else None,
                "top1_page": r["candidates"][0]["pdf_page"] if r["candidates"] else None,
                "note": r.get("note", ""),
            }
            for r in results
        ],
    }
    with OUT_MANIFEST.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"清单写入: {OUT_MANIFEST}")
    print(f"\n统计: {json.dumps(stats, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
