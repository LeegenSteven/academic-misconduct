# -*- coding: utf-8 -*-
"""
任务3b（复用版）：BM25 top-10 vs MonoT5 top-10 接入 MultiVerS，全量 316 Dev
- 有证据 255 条：复用 task3a 的 bm25_rank/monot5_rank 排序（含 text）
- 无证据 61 条：补算 BM25 top50 + MonoT5 排序
gold 使用 v2 三分类（方案 B：IRRELEVANT 单独统计）。
"""
import json, math, re, time
from collections import Counter
from pathlib import Path

import torch
from torch import nn
from transformers import LongformerTokenizerFast, LongformerModel, T5ForConditionalGeneration, T5Tokenizer

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
MT5 = str(WORK / "hf_cache" / "hub" / "models--castorini--monot5-base-med-msmarco" / "snapshots" / "7a4324f2785ab5f1dea00e7a39d6f81f3e2d273f")
T3A = OUTPUTS / "task3_six_retrieval_result_2026-09-16.json"

LABEL_LOOKUP = {0: "NOT_ACCURATE", 1: "NEI", 2: "ACCURATE"}
KB, KM = 10, 10


class LabelHead(nn.Module):
    def __init__(self, hidden_size, num_labels, dropout_p):
        super().__init__()
        self.fc1 = nn.Linear(hidden_size, hidden_size)
        self.act = nn.GELU()
        self.dropout = nn.Dropout(dropout_p)
        self.fc2 = nn.Linear(hidden_size, num_labels)

    def forward(self, pooled):
        return self.fc2(self.dropout(self.act(self.fc1(pooled))))


def load_multivers():
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


def predict(tokenizer, encoder, head, claim, sents):
    tokenized = tokenize_for_multivers(tokenizer, claim, sents)
    with torch.no_grad():
        encoded = encoder(**tokenized)
        logits = head(encoded.pooler_output)
    return int(logits.argmax(dim=1)[0])


def main():
    print("[1/6] 加载模型...", flush=True)
    tok_mv, enc, head = load_multivers()
    tok_t5 = T5Tokenizer.from_pretrained(MT5, use_fast=False, local_files_only=True)
    mt5 = T5ForConditionalGeneration.from_pretrained(MT5, local_files_only=True); mt5.eval()
    true_id = tok_t5("true", add_special_tokens=False).input_ids[0]
    false_id = tok_t5("false", add_special_tokens=False).input_ids[0]

    print("[2/6] 加载 v2 Dev + corpus + 3a 排序结果...", flush=True)
    claims = [json.loads(x) for x in open(V2_DEV, encoding="utf-8") if x.strip()]
    corpus = {}
    for line in open(CORPUS, encoding="utf-8"):
        x = json.loads(line); corpus[int(x["doc_id"])] = x.get("abstract", [])
    t3a = json.load(open(T3A, encoding="utf-8"))
    t3a_by_id = {r["claim_id"]: r for r in t3a["results"]}
    print(f"      Dev {len(claims)} 条，3a 有 {len(t3a_by_id)} 条排序", flush=True)

    print(f"[3/6] 构造两组输入（BM25 top-{KB} / MonoT5 top-{KM}）...", flush=True)
    rows = []
    n_need_mt5 = 0
    for c in claims:
        cid = int(c["id"])
        pre = t3a_by_id.get(cid)
        if pre and pre.get("monot5_rank"):
            bm_rank = pre["bm25_rank"]; mt_rank = pre["monot5_rank"]
        else:
            n_need_mt5 += 1
            cand = [(int(d), i, s) for d in c["cited_doc_ids"] for i, s in enumerate(corpus.get(int(d), []))]
            if cand:
                lex = bm25(toks(c["claim"]), [toks(x[2]) for x in cand])
                bm25_order = sorted(range(len(cand)), key=lambda i: lex[i], reverse=True)[:50]
                bm_rank = [{"doc_id": cand[i][0], "sentence_index": cand[i][1], "text": cand[i][2]} for i in bm25_order]
                prompts = [f"Query: {c['claim']} Document: {cand[i][2]} Relevant:" for i in bm25_order]
                scores = []
                for j in range(0, len(prompts), 16):
                    batch = prompts[j:j+16]
                    inp = tok_t5(batch, return_tensors="pt", padding=True, truncation=True, max_length=512)
                    with torch.no_grad():
                        logits = mt5(**inp, decoder_input_ids=torch.full((len(batch), 1), mt5.config.decoder_start_token_id, dtype=torch.long)).logits[:, -1, :]
                    lp = torch.log_softmax(logits[:, [true_id, false_id]], dim=-1)[:, 0].tolist()
                    scores.extend(lp)
                ranked = sorted(range(len(bm25_order)), key=lambda j: scores[j], reverse=True)
                mt_rank = [bm_rank[j] for j in ranked]
            else:
                bm_rank, mt_rank = [], []
        rows.append({"claim_id": cid, "claim": c["claim"], "gold": c["gold"],
                     "_bm": [x["text"] for x in bm_rank[:KB]],
                     "_mt": [corpus.get(x["doc_id"], [])[x["sentence_index"]] if x["sentence_index"] < len(corpus.get(x["doc_id"], [])) else "" for x in mt_rank[:KM]]})
    print(f"      补算 MonoT5 排序的样本: {n_need_mt5}", flush=True)

    print("[4/6] MultiVerS 两组推理（CPU）...", flush=True)
    t0 = time.time()
    for i, r in enumerate(rows):
        r["pred_bm25"] = LABEL_LOOKUP[predict(tok_mv, enc, head, r["claim"], r["_bm"])] if r["_bm"] else "NEI"
        r["pred_mt5"] = LABEL_LOOKUP[predict(tok_mv, enc, head, r["claim"], r["_mt"])] if r["_mt"] else "NEI"
        r.pop("_bm"); r.pop("_mt")
        if (i + 1) % 50 == 0 or i + 1 == len(rows):
            print(f"      {i+1}/{len(rows)} ({time.time()-t0:.0f}s)", flush=True)

    print("[5/6] 指标（方案B）...", flush=True)
    def metric(pk):
        sub = [r for r in rows if r["gold"] != "IRRELEVANT"]
        acc = sum(1 for r in sub if r[pk] == r["gold"]) / len(sub)
        cls = {}
        for g in ("ACCURATE", "NOT_ACCURATE"):
            tp = sum(1 for r in sub if r["gold"] == g and r[pk] == g)
            fp = sum(1 for r in sub if r["gold"] != g and r[pk] == g)
            fn = sum(1 for r in sub if r["gold"] == g and r[pk] != g)
            p_ = tp / (tp + fp) if tp + fp else 0
            r_ = tp / (tp + fn) if tp + fn else 0
            f1 = 2 * p_ * r_ / (p_ + r_) if p_ + r_ else 0
            cls[g] = {"P": round(p_, 4), "R": round(r_, 4), "F1": round(f1, 4), "n": tp + fn}
        macro = sum(m["F1"] for m in cls.values()) / 2
        return {"accuracy_sub": round(acc, 4), "correct": sum(1 for r in sub if r[pk] == r["gold"]),
                "sub_total": len(sub), "per_class": cls, "macro_f1": round(macro, 4),
                "irrelevant_pred_dist": dict(Counter(r[pk] for r in rows if r["gold"] == "IRRELEVANT")),
                "pred_dist": dict(Counter(r[pk] for r in rows))}

    m1 = metric("pred_bm25"); m2 = metric("pred_mt5")
    out = {"task": f"任务3b：MultiVerS 全量316 Dev，BM25 top-{KB} vs MonoT5 top-{KM}（复用3a排序）",
           "n_claims": len(rows), "metric_bm25": m1, "metric_monot5": m2,
           "elapsed_seconds": round(time.time() - t0, 2),
           "results": [{k: v for k, v in r.items()} for r in rows]}
    out_path = OUTPUTS / f"task3b_multivers_cmp_b{KB}_m{KM}_2026-09-16.json"
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n=== 全量316 Dev（方案B）===")
    print(f"BM25 top-{KB}: acc={m1['accuracy_sub']} ({m1['correct']}/{m1['sub_total']}) Macro-F1={m1['macro_f1']} 预测分布={m1['pred_dist']}")
    print(f"MonoT5 top-{KM}: acc={m2['accuracy_sub']} ({m2['correct']}/{m2['sub_total']}) Macro-F1={m2['macro_f1']} 预测分布={m2['pred_dist']}")
    print("结果已存:", out_path)


if __name__ == "__main__":
    main()
