# -*- coding: utf-8 -*-
"""
Sarol Dev 集两组对照（周报任务1）
================================
同一权重（scifact.ckpt，SciFact 预训练，跨数据集迁移）在 Sarol Dev 集上：
  A 金标准证据块输入：gold evidence 句子作为输入
  B BM25 top-20 候选块输入：按被引文献分组检索的 top-20 句子作为输入
输出：两组 claim 级三分类预测 + 评估（准确率/混淆矩阵/逐条对照表）
"""
import json
import math
import re
import time
from collections import Counter
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn
from transformers import LongformerTokenizerFast, LongformerModel

import pytorch_lightning.utilities.argparse as _pla
for _n in ["_gpus_arg_default", "_tpu_arg_default", "_get_gpus_arg_default"]:
    if not hasattr(_pla, _n):
        setattr(_pla, _n, lambda *a, **k: None)

WORK = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work")
OUTPUTS = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\outputs")
CKPT = WORK / "checkpoints" / "scifact.ckpt"
ENCODER_DIR = WORK / "longformer-large-4096"
DEV_JSONL = WORK / "converted-three-class" / "claims-dev.jsonl"
CORPUS = WORK / "Citation-Integrity-main" / "Data" / "multivers-format" / "corpus.jsonl"

LABEL_LOOKUP = {0: "NOT_ACCURATE", 1: "NEI", 2: "ACCURATE"}


class LabelHead(nn.Module):
    def __init__(self, hidden_size, num_labels, dropout_p):
        super().__init__()
        self.fc1 = nn.Linear(hidden_size, hidden_size)
        self.act = nn.GELU()
        self.dropout = nn.Dropout(dropout_p)
        self.fc2 = nn.Linear(hidden_size, num_labels)

    def forward(self, pooled):
        return self.fc2(self.dropout(self.act(self.fc1(pooled))))


def load_model():
    d = torch.load(CKPT, map_location="cpu", weights_only=False)
    sd = d["state_dict"]
    enc_sd = {k[len("encoder."):]: v for k, v in sd.items() if k.startswith("encoder.")}
    head_sd = {k[len("label_classifier."):]: v for k, v in sd.items() if k.startswith("label_classifier.")}
    vocab_size = enc_sd["embeddings.word_embeddings.weight"].shape[0]
    hidden = enc_sd["embeddings.word_embeddings.weight"].shape[1]

    tokenizer = LongformerTokenizerFast.from_pretrained(str(ENCODER_DIR))
    encoder = LongformerModel.from_pretrained(str(ENCODER_DIR))
    if encoder.config.vocab_size != vocab_size:
        encoder.resize_token_embeddings(vocab_size)
    encoder.load_state_dict(enc_sd, strict=False)
    encoder.eval()

    head = LabelHead(hidden, 3, encoder.config.hidden_dropout_prob)
    head_mapped = {k.replace("_linear_layers.0", "fc1").replace("_linear_layers.1", "fc2"): v
                   for k, v in head_sd.items()}
    head.load_state_dict(head_mapped)
    head.eval()
    return tokenizer, encoder, head


def tokenize_for_multivers(tokenizer, claim, evidence_sents):
    text = tokenizer.eos_token.join([claim] + list(evidence_sents)) + tokenizer.eos_token
    tokenized = tokenizer(text, padding=False, return_tensors="pt")
    input_ids = tokenized["input_ids"][0][: 4090]  # 留余量
    attention_mask = torch.ones_like(input_ids).unsqueeze(0)
    first_eos = (input_ids == tokenizer.eos_token_id).nonzero()[0][0].item()
    is_claim = torch.arange(len(input_ids)) < first_eos
    is_special = (input_ids == tokenizer.bos_token_id) | (input_ids == tokenizer.eos_token_id)
    global_attention = (is_special | is_claim).to(torch.long).unsqueeze(0)
    return {"input_ids": input_ids.unsqueeze(0), "attention_mask": attention_mask,
            "global_attention_mask": global_attention}


def toks(s):
    return re.findall(r"[A-Za-z0-9]+", s.lower())


def bm25_scores(q, docs):
    n = len(docs)
    avg = sum(map(len, docs)) / max(n, 1)
    dfs = Counter(t for d in docs for t in set(d))
    out = []
    for d in docs:
        tf = Counter(d)
        z = 0.0
        for t in q:
            if t not in tf:
                continue
            idf = math.log(1 + (n - dfs[t] + 0.5) / (dfs[t] + 0.5))
            z += idf * tf[t] * 2.5 / (tf[t] + 1.5 * (0.25 + 0.75 * len(d) / max(avg, 1)))
        out.append(z)
    return out


def load_data():
    claims = [json.loads(x) for x in open(DEV_JSONL, encoding="utf-8") if x.strip()]
    corpus = {}
    for line in open(CORPUS, encoding="utf-8"):
        x = json.loads(line)
        corpus[int(x["doc_id"])] = x.get("abstract", [])
    return claims, corpus


def gold_sentences(claim):
    """金标准证据句：[(doc_id, sentence_index, text, label)]"""
    out = []
    for doc_id, evs in claim.get("evidence", {}).items():
        for ev in evs:
            for sidx in ev.get("sentences", []):
                out.append((int(doc_id), int(sidx), ev.get("label")))
    return out


def bm25_top_k(claim, corpus, k=20):
    """按被引文献分组 BM25 检索 top-k 句子"""
    cand = [(int(d), i, s) for d in claim["cited_doc_ids"]
            for i, s in enumerate(corpus.get(int(d), []))]
    if not cand:
        return []
    lex = bm25_scores(toks(claim["claim"]), [toks(x[2]) for x in cand])
    order = sorted(range(len(cand)), key=lambda i: lex[i], reverse=True)[:k]
    return [(cand[i][0], cand[i][1], cand[i][2]) for i in order]


def claim_gold_label(claim):
    labels = [ev.get("label") for evs in claim.get("evidence", {}).values() for ev in evs]
    if not labels:
        return "NEI"
    if any(l == "NOT_ACCURATE" for l in labels):
        return "NOT_ACCURATE"
    return "ACCURATE"


def predict(tokenizer, encoder, head, claim, sents):
    tokenized = tokenize_for_multivers(tokenizer, claim, sents)
    with torch.no_grad():
        encoded = encoder(**tokenized)
        logits = head(encoded.pooler_output)
    return int(logits.argmax(dim=1)[0])


def main():
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print("[1/5] 加载模型...", flush=True)
    tokenizer, encoder, head = load_model()

    print("[2/5] 加载 Dev 数据...", flush=True)
    claims, corpus = load_data()
    if limit:
        claims = claims[:limit]
    print(f"      Dev {len(claims)} 条", flush=True)

    print("[3/5] 构造两组输入（A金标准 / B BM25 top-20）...", flush=True)
    rows = []
    n_gold_empty = 0
    n_bm25_empty = 0
    for c in claims:
        g = gold_sentences(c)
        g_sents = [(d, s, t) for d, s, t in g]
        b = bm25_top_k(c, corpus, k=20)
        g_texts = [corpus.get(d, [])[s] if s < len(corpus.get(d, [])) else "" for d, s, t in g_sents]
        b_texts = [t for _, _, t in b]
        g_texts = [t for t in g_texts if t]
        if not g_texts:
            n_gold_empty += 1
        if not b_texts:
            n_bm25_empty += 1
        rows.append({
            "claim_id": int(c["id"]),
            "claim": c["claim"],
            "gold": claim_gold_label(c),
            "gold_sentences": [{"doc_id": d, "sentence_index": s, "label": lbl} for d, s, lbl in g_sents],
            "bm25_sentences": [{"doc_id": d, "sentence_index": s} for d, s, _ in b],
            "_g_texts": g_texts,
            "_b_texts": b_texts,
        })
    print(f"      金标准无句: {n_gold_empty}，BM25 无候选: {n_bm25_empty}", flush=True)

    print("[4/5] 两组推理（CPU）...", flush=True)
    t0 = time.time()
    for i, r in enumerate(rows):
        pa = predict(tokenizer, encoder, head, r["claim"], r["_g_texts"]) if r["_g_texts"] else 1
        pb = predict(tokenizer, encoder, head, r["claim"], r["_b_texts"]) if r["_b_texts"] else 1
        r["pred_gold_input"] = LABEL_LOOKUP[pa]
        r["pred_bm25_input"] = LABEL_LOOKUP[pb]
        r.pop("_g_texts")
        r.pop("_b_texts")
        if (i + 1) % 50 == 0 or i + 1 == len(rows):
            print(f"      {i+1}/{len(rows)} ({time.time()-t0:.0f}s)", flush=True)

    print("[5/5] 评估与保存...", flush=True)
    acc_a = sum(1 for r in rows if r["pred_gold_input"] == r["gold"]) / len(rows)
    acc_b = sum(1 for r in rows if r["pred_bm25_input"] == r["gold"]) / len(rows)
    dist_a = Counter(r["pred_gold_input"] for r in rows)
    dist_b = Counter(r["pred_bm25_input"] for r in rows)
    gold_dist = Counter(r["gold"] for r in rows)

    out = {
        "status": "completed",
        "task": "Sarol Dev 两组对照（金标准 vs BM25 top-20）",
        "weight": "scifact.ckpt（SciFact 预训练，跨数据集迁移）",
        "device": "cpu",
        "claims": len(rows),
        "gold_distribution": dict(gold_dist),
        "accuracy_gold_input": round(acc_a, 4),
        "accuracy_bm25_input": round(acc_b, 4),
        "pred_distribution_gold_input": dict(dist_a),
        "pred_distribution_bm25_input": dict(dist_b),
        "elapsed_seconds": round(time.time() - t0, 2),
        "results": [{k: v for k, v in r.items()} for r in rows],
    }
    out_path = OUTPUTS / "multivers_dev_contrast_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"金标准输入准确率: {acc_a:.4f}（分布 {dict(dist_a)}）", flush=True)
    print(f"BM25 top-20 输入准确率: {acc_b:.4f}（分布 {dict(dist_b)}）", flush=True)
    print(f"gold 分布: {dict(gold_dist)}", flush=True)
    print(f"耗时 {out['elapsed_seconds']}s，结果已存 {out_path}", flush=True)


if __name__ == "__main__":
    main()
