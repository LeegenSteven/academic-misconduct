# -*- coding: utf-8 -*-
"""
任务2：255 条有人工证据 Dev 子集，三种输入对照
  A 金标准证据句（复用已有推理）
  B 金标准句所在完整块（新推理）
  C BM25 top-20 候选句（复用已有推理）
记录文本长度、截断情况；分析上下文缺失与候选遗漏；无证据样本单独说明。
gold 使用 v2 三分类（255 子集内为 ACCURATE / NOT_ACCURATE）。
"""
import json
import math
import re
import time
from collections import Counter
from pathlib import Path

import torch
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
V2_DEV = WORK / "converted-three-class-v2" / "claims-dev.jsonl"
CORPUS = WORK / "Citation-Integrity-main" / "Data" / "multivers-format" / "corpus.jsonl"
RESULT = OUTPUTS / "multivers_dev_contrast_result.json"

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


def tokenize_for_multivers(tokenizer, claim, evidence_sents, max_len=4090):
    text = tokenizer.eos_token.join([claim] + list(evidence_sents)) + tokenizer.eos_token
    tokenized = tokenizer(text, padding=False, return_tensors="pt")
    input_ids = tokenized["input_ids"][0][:max_len]
    attention_mask = torch.ones_like(input_ids).unsqueeze(0)
    first_eos = (input_ids == tokenizer.eos_token_id).nonzero()[0][0].item()
    is_claim = torch.arange(len(input_ids)) < first_eos
    is_special = (input_ids == tokenizer.bos_token_id) | (input_ids == tokenizer.eos_token_id)
    global_attention = (is_special | is_claim).to(torch.long).unsqueeze(0)
    return {"input_ids": input_ids.unsqueeze(0), "attention_mask": attention_mask,
            "global_attention_mask": global_attention}, len(tokenized["input_ids"][0])


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
    claims = [json.loads(x) for x in open(V2_DEV, encoding="utf-8") if x.strip()]
    corpus = {}
    for line in open(CORPUS, encoding="utf-8"):
        x = json.loads(line)
        corpus[int(x["doc_id"])] = x.get("abstract", [])
    return claims, corpus


def gold_sentences(claim):
    out = []
    for doc_id, evs in claim.get("evidence", {}).items():
        for ev in evs:
            for sidx in ev.get("sentences", []):
                out.append((int(doc_id), int(sidx), ev.get("label")))
    return out


def bm25_top_k(claim, corpus, k=20):
    cand = [(int(d), i, s) for d in claim["cited_doc_ids"]
            for i, s in enumerate(corpus.get(int(d), []))]
    if not cand:
        return []
    lex = bm25_scores(toks(claim["claim"]), [toks(x[2]) for x in cand])
    order = sorted(range(len(cand)), key=lambda i: lex[i], reverse=True)[:k]
    return [(cand[i][0], cand[i][1], cand[i][2]) for i in order]


def predict(tokenizer, encoder, head, claim, sents):
    tokenized, _ = tokenize_for_multivers(tokenizer, claim, sents)
    with torch.no_grad():
        encoded = encoder(**tokenized)
        logits = head(encoded.pooler_output)
    return int(logits.argmax(dim=1)[0])


def main():
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    print("[1/5] 加载模型...", flush=True)
    tokenizer, encoder, head = load_model()

    print("[2/5] 加载 v2 Dev + corpus + 已有结果...", flush=True)
    claims, corpus = load_data()
    old = json.load(open(RESULT, encoding="utf-8"))
    old_by_id = {x["claim_id"]: x for x in old["results"]}

    # 255 条有证据子集（v2 中 evidence_missing 不存在）
    ev_claims = [c for c in claims if not c.get("evidence_missing")]
    if limit:
        ev_claims = ev_claims[:limit]
    n_noev = len(claims) - len(ev_claims)
    print(f"      v2 Dev {len(claims)} 条，有证据 {len(ev_claims)} 条（本次子集），无证据 {n_noev} 条（单独说明，不参与）", flush=True)

    print("[3/5] 构造三组输入 + 统计长度/截断...", flush=True)
    rows = []
    for c in ev_claims:
        cid = int(c["id"])
        gold = c["gold"]
        # A 金标准句（复用）
        old_row = old_by_id.get(cid, {})
        pred_a = old_row.get("pred_gold_input")
        # C BM25（复用）
        pred_c = old_row.get("pred_bm25_input")
        # B 金标准句所在完整块：gold 句子涉及 doc 的完整 abstract
        gs = gold_sentences(c)
        g_docs = sorted({d for d, _, _ in gs})
        block_sents = [s for d in g_docs for s in corpus.get(d, [])]
        # 长度统计
        def stats(sents):
            _, full_len = tokenize_for_multivers(tokenizer, c["claim"], sents)
            return {"n_sent": len(sents), "tok_full": full_len, "truncated": full_len > 4090}
        st_a = stats([corpus.get(d, [])[s] if s < len(corpus.get(d, [])) else "" for d, s, _ in gs if s < len(corpus.get(d, []))])
        st_b = stats(block_sents)
        bm = bm25_top_k(c, corpus, k=20)
        st_c = stats([t for _, _, t in bm])
        rows.append({
            "claim_id": cid, "claim": c["claim"], "gold": gold,
            "n_gold_sent": len(gs), "n_gold_docs": len(g_docs),
            "sent_gold": st_a, "sent_block": st_b, "sent_bm25": st_c,
            "bm25_recall_gold_sent": None,  # 下方计算
            "pred_gold_sent": pred_a, "pred_gold_block": None, "pred_bm25": pred_c,
        })

    # BM25 对金标准句的召回（句级）
    for r in rows:
        c = next(x for x in ev_claims if int(x["id"]) == r["claim_id"])
        gs = gold_sentences(c)
        gset = {(d, s) for d, s, _ in gs}
        bm = bm25_top_k(c, corpus, k=20)
        bset = {(d, s) for d, s, _ in bm}
        r["bm25_recall_gold_sent"] = round(len(gset & bset) / len(gset), 4) if gset else None
    print(f"      BM25 对金标准句句级召回均值: {sum(r['bm25_recall_gold_sent'] or 0 for r in rows)/len(rows):.4f}", flush=True)

    print("[4/5] 推理 B 组（金标准句所在完整块，CPU）...", flush=True)
    t0 = time.time()
    for i, r in enumerate(rows):
        c = next(x for x in ev_claims if int(x["id"]) == r["claim_id"])
        gs = gold_sentences(c)
        g_docs = sorted({d for d, _, _ in gs})
        block_sents = [s for d in g_docs for s in corpus.get(d, [])]
        r["pred_gold_block"] = LABEL_LOOKUP[predict(tokenizer, encoder, head, c["claim"], block_sents)]
        if (i + 1) % 25 == 0 or i + 1 == len(rows):
            print(f"      {i+1}/{len(rows)} ({time.time()-t0:.0f}s)", flush=True)

    print("[5/5] 评估与保存...", flush=True)
    def metric(pk):
        total = len(rows)
        correct = sum(1 for r in rows if r[pk] == r["gold"])
        acc = correct / total
        cls = {}
        for g in ("ACCURATE", "NOT_ACCURATE"):
            tp = sum(1 for r in rows if r["gold"] == g and r[pk] == g)
            fp = sum(1 for r in rows if r["gold"] != g and r[pk] == g)
            fn = sum(1 for r in rows if r["gold"] == g and r[pk] != g)
            p_ = tp / (tp + fp) if tp + fp else 0
            r_ = tp / (tp + fn) if tp + fn else 0
            f1 = 2 * p_ * r_ / (p_ + r_) if p_ + r_ else 0
            cls[g] = {"P": round(p_, 4), "R": round(r_, 4), "F1": round(f1, 4), "n": tp + fn}
        macro = sum(m["F1"] for m in cls.values()) / 2
        return {"accuracy": round(acc, 4), "correct": correct, "total": total,
                "per_class": cls, "macro_f1": round(macro, 4)}

    m_a = metric("pred_gold_sent")
    m_b = metric("pred_gold_block")
    m_c = metric("pred_bm25")

    out = {
        "task": "任务2：255条有证据Dev子集三种输入对照",
        "weight": "scifact.ckpt",
        "device": "cpu",
        "n_claims": len(rows),
        "n_no_evidence": n_noev,
        "gold_dist": dict(Counter(r["gold"] for r in rows)),
        "metric_gold_sent": m_a,
        "metric_gold_block": m_b,
        "metric_bm25": m_c,
        "avg_length": {
            "gold_sent": {k: round(sum(r["sent_gold"][k] for r in rows)/len(rows), 2) for k in ("n_sent", "tok_full")},
            "gold_block": {k: round(sum(r["sent_block"][k] for r in rows)/len(rows), 2) for k in ("n_sent", "tok_full")},
            "bm25": {k: round(sum(r["sent_bm25"][k] for r in rows)/len(rows), 2) for k in ("n_sent", "tok_full")},
        },
        "truncated_count": {
            "gold_sent": sum(1 for r in rows if r["sent_gold"]["truncated"]),
            "gold_block": sum(1 for r in rows if r["sent_block"]["truncated"]),
            "bm25": sum(1 for r in rows if r["sent_bm25"]["truncated"]),
        },
        "bm25_gold_sent_recall": round(sum(r["bm25_recall_gold_sent"] or 0 for r in rows)/len(rows), 4),
        "elapsed_seconds": round(time.time() - t0, 2),
        "results": [{k: v for k, v in r.items()} for r in rows],
    }
    out_path = OUTPUTS / "task2_three_inputs_result_2026-09-16.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n=== 指标（255有证据子集，v2 gold）===")
    for name, m in (("A 金标准句", m_a), ("B 金标准块", m_b), ("C BM25 top-20", m_c)):
        print(f"{name}: acc={m['accuracy']} ({m['correct']}/{m['total']}) Macro-F1={m['macro_f1']} 各类={m['per_class']}")
    print("平均长度(句数/token):", out["avg_length"])
    print("截断条数:", out["truncated_count"])
    print("BM25 对金标准句句级召回:", out["bm25_gold_sent_recall"])
    print("结果已存:", out_path)


if __name__ == "__main__":
    main()
