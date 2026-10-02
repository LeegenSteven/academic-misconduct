# -*- coding: utf-8 -*-
"""
任务4评估：微调后模型 on Dev 316（BM25 top-10 输入，与 3b 同口径对比）
输出：方案B acc/Macro-F1、各类 P/R/F1、NOT_ACCURATE 召回、IRRELEVANT 预测分布
"""
import json, math, re, sys, time
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
ENCODER_DIR = WORK / "longformer-large-4096"
V2_DEV = WORK / "converted-three-class-v2" / "claims-dev.jsonl"
CORPUS = WORK / "Citation-Integrity-main" / "Data" / "multivers-format" / "corpus.jsonl"
FINETUNED = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUTS / "task4_finetuned_full_step2141.pt"

LABEL_LOOKUP = {0: "NOT_ACCURATE", 1: "NEI", 2: "ACCURATE"}  # 推理用原3类槽位
KB = 10


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
    enc_sd = torch.load(FINETUNED, map_location="cpu", weights_only=False)
    tokenizer = LongformerTokenizerFast.from_pretrained(str(ENCODER_DIR))
    encoder = LongformerModel.from_pretrained(str(ENCODER_DIR))
    hidden = encoder.config.hidden_size
    if encoder.config.vocab_size != enc_sd["encoder"]["embeddings.word_embeddings.weight"].shape[0]:
        encoder.resize_token_embeddings(enc_sd["encoder"]["embeddings.word_embeddings.weight"].shape[0])
    encoder.load_state_dict(enc_sd["encoder"])
    encoder.eval()
    head = LabelHead(hidden, 3, encoder.config.hidden_dropout_prob)
    head.load_state_dict(enc_sd["head"])
    head.eval()
    return tokenizer, encoder, head


def tokenize_for_multivers(tokenizer, claim, sents):
    text = tokenizer.eos_token.join([claim] + list(sents)) + tokenizer.eos_token
    tokenized = tokenizer(text, padding=False, return_tensors="pt")
    input_ids = tokenized["input_ids"][0][:4090]
    attention_mask = torch.ones_like(input_ids).unsqueeze(0)
    first_eos = (input_ids == tokenizer.eos_token_id).nonzero()[0][0].item()
    is_claim = torch.arange(len(input_ids)) < first_eos
    is_special = (input_ids == tokenizer.bos_token_id) | (input_ids == tokenizer.eos_token_id)
    global_attention = (is_special | is_claim).to(torch.long).unsqueeze(0)
    return {"input_ids": input_ids.unsqueeze(0), "attention_mask": attention_mask,
            "global_attention_mask": global_attention}


def toks(s): return re.findall(r"[A-Za-z0-9]+", s.lower())


def bm25(q, docs):
    n = len(docs); avg = sum(map(len, docs)) / max(n, 1); dfs = Counter(t for d in docs for t in set(d)); out = []
    for d in docs:
        tf = Counter(d); z = 0.0
        for t in q:
            if t not in tf: continue
            idf = math.log(1 + (n - dfs[t] + 0.5) / (dfs[t] + 0.5))
            z += idf * tf[t] * 2.5 / (tf[t] + 1.5 * (0.25 + 0.75 * len(d) / max(avg, 1)))
        out.append(z)
    return out


def main():
    print("[1/4] 加载微调后模型...", flush=True)
    tokenizer, encoder, head = load_model()
    claims = [json.loads(x) for x in open(V2_DEV, encoding="utf-8") if x.strip()]
    corpus = {}
    for line in open(CORPUS, encoding="utf-8"):
        x = json.loads(line); corpus[int(x["doc_id"])] = x.get("abstract", [])
    print(f"      Dev {len(claims)} 条", flush=True)

    print(f"[2/4] 构造 BM25 top-{KB} 输入...", flush=True)
    rows = []
    for c in claims:
        cand = [(int(d), i, s) for d in c["cited_doc_ids"] for i, s in enumerate(corpus.get(int(d), []))]
        sents = []
        if cand:
            lex = bm25(toks(c["claim"]), [toks(x[2]) for x in cand])
            order = sorted(range(len(cand)), key=lambda i: lex[i], reverse=True)[:KB]
            sents = [cand[i][2] for i in order]
        rows.append({"claim_id": int(c["id"]), "claim": c["claim"], "gold": c["gold"], "_s": sents})

    print("[3/4] MultiVerS 推理（CPU）...", flush=True)
    t0 = time.time()
    for i, r in enumerate(rows):
        r["pred"] = LABEL_LOOKUP[1] if not r["_s"] else None
        if r["_s"]:
            tok = tokenize_for_multivers(tokenizer, r["claim"], r["_s"])
            with torch.no_grad():
                out = encoder(**tok)
                logits = head(out.pooler_output)
            r["pred"] = LABEL_LOOKUP[int(logits.argmax(dim=1)[0])]
        r.pop("_s")
        if (i + 1) % 50 == 0 or i + 1 == len(rows):
            print(f"      {i+1}/{len(rows)} ({time.time()-t0:.0f}s)", flush=True)

    print("[4/4] 指标（方案B）...", flush=True)
    sub = [r for r in rows if r["gold"] != "IRRELEVANT"]
    acc = sum(1 for r in sub if r["pred"] == r["gold"]) / len(sub)
    cls = {}
    for g in ("ACCURATE", "NOT_ACCURATE"):
        tp = sum(1 for r in sub if r["gold"] == g and r["pred"] == g)
        fp = sum(1 for r in sub if r["gold"] != g and r["pred"] == g)
        fn = sum(1 for r in sub if r["gold"] == g and r["pred"] != g)
        p_ = tp / (tp + fp) if tp + fp else 0
        r_ = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * p_ * r_ / (p_ + r_) if p_ + r_ else 0
        cls[g] = {"P": round(p_, 4), "R": round(r_, 4), "F1": round(f1, 4), "n": tp + fn}
    macro = sum(m["F1"] for m in cls.values()) / 2
    irr_dist = dict(Counter(r["pred"] for r in rows if r["gold"] == "IRRELEVANT"))
    pred_dist = dict(Counter(r["pred"] for r in rows))
    out = {"task": "任务4：微调后 Dev 316（BM25 top-10）",
           "n_claims": len(rows), "accuracy_sub": round(acc, 4),
           "correct": sum(1 for r in sub if r["pred"] == r["gold"]), "sub_total": len(sub),
           "per_class": cls, "macro_f1": round(macro, 4),
           "not_accurate_recall": cls["NOT_ACCURATE"]["R"],
           "irrelevant_pred_dist": irr_dist, "pred_dist": pred_dist,
           "elapsed_seconds": round(time.time() - t0, 2),
           "results": [{k: v for k, v in r.items()} for r in rows]}
    out_path = OUTPUTS / f"task4_finetuned_dev_eval_{FINETUNED.stem}_2026-09-17.json"
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n=== 微调后 Dev 316（BM25 top-10）===")
    print(f"acc={out['accuracy_sub']} ({out['correct']}/{out['sub_total']}) Macro-F1={out['macro_f1']}")
    print(f"per_class={cls}")
    print(f"NOT_ACCURATE 召回={out['not_accurate_recall']}")
    print(f"IRRELEVANT 预测分布={irr_dist}")
    print(f"整体预测分布={pred_dist}")
    print("结果已存:", out_path)


if __name__ == "__main__":
    main()
