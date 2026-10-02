# -*- coding: utf-8 -*-
"""
任务3第一步：step2141 在 2141 条 Train 上自评
口径与 Dev/Test 完全一致：BM25 top-10 句输入
输出每条：claim_id, gold, pred, 三类概率(softmax)，以及难样本统计
难样本定义（可复现）：
  A. gold=NOT_ACCURATE 且 pred != NOT_ACCURATE（判错的歪曲样本）
  B. gold=NOT_ACCURATE 且 pred == NOT_ACCURATE 且 正确类概率 < LOW_CONF（判对但低置信）
"""
import json, math, re, sys, time
from collections import Counter
from pathlib import Path

import torch
from torch import nn
import torch.nn.functional as F
from transformers import LongformerTokenizerFast, LongformerModel

import pytorch_lightning.utilities.argparse as _pla
for _n in ["_gpus_arg_default", "_tpu_arg_default", "_get_gpus_arg_default"]:
    if not hasattr(_pla, _n):
        setattr(_pla, _n, lambda *a, **k: None)

WORK = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work")
OUTPUTS = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\outputs")
ENCODER_DIR = WORK / "longformer-large-4096"
V2_TRAIN = WORK / "converted-three-class-v2" / "claims-train.jsonl"
CORPUS = WORK / "Citation-Integrity-main" / "Data" / "multivers-format" / "corpus.jsonl"
FINETUNED = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUTS / "task4_finetuned_full_step2141.pt"

LABEL_LOOKUP = {0: "NOT_ACCURATE", 1: "NEI", 2: "ACCURATE"}
CLASSES = ["NOT_ACCURATE", "NEI", "ACCURATE"]  # 与 logits 列对齐
KB = 10
LOW_CONF = 0.6  # 低置信阈值：正确类概率低于此值记为低置信


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
    claims = [json.loads(x) for x in open(V2_TRAIN, encoding="utf-8") if x.strip()]
    corpus = {}
    for line in open(CORPUS, encoding="utf-8"):
        x = json.loads(line); corpus[int(x["doc_id"])] = x.get("abstract", [])
    print(f"      Train {len(claims)} 条", flush=True)

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

    print("[3/4] Train 自评推理（CPU）...", flush=True)
    t0 = time.time()
    for i, r in enumerate(rows):
        if not r["_s"]:
            # 无证据句：和 Dev/Test 一样直接判 NEI
            r["pred"] = "NEI"
            r["probs"] = {"NOT_ACCURATE": 0.0, "NEI": 1.0, "ACCURATE": 0.0}
        else:
            tok = tokenize_for_multivers(tokenizer, r["claim"], r["_s"])
            with torch.no_grad():
                out = encoder(**tok)
                logits = head(out.pooler_output)
                probs = F.softmax(logits, dim=1)[0].tolist()
            r["pred"] = LABEL_LOOKUP[int(logits.argmax(dim=1)[0])]
            r["probs"] = {CLASSES[j]: round(probs[j], 4) for j in range(3)}
        r.pop("_s")
        if (i + 1) % 100 == 0 or i + 1 == len(rows):
            print(f"      {i+1}/{len(rows)} ({time.time()-t0:.0f}s)", flush=True)

    print("[4/4] 难样本统计...", flush=True)
    # A: gold=NA 判错
    hard_wrong = [r for r in rows if r["gold"] == "NOT_ACCURATE" and r["pred"] != "NOT_ACCURATE"]
    # B: gold=NA 判对但低置信
    low_conf_right = [r for r in rows if r["gold"] == "NOT_ACCURATE" and r["pred"] == "NOT_ACCURATE"
                      and r["probs"]["NOT_ACCURATE"] < LOW_CONF]
    # 顺带：gold 分布、pred 分布
    gold_dist = dict(Counter(r["gold"] for r in rows))
    pred_dist = dict(Counter(r["pred"] for r in rows))
    # NA 子集混淆
    na_total = sum(1 for r in rows if r["gold"] == "NOT_ACCURATE")
    out = {
        "task": "任务3第一步：Train 自评挖难样本",
        "checkpoint": str(FINETUNED),
        "kb": KB, "low_conf_threshold": LOW_CONF,
        "n_train": len(rows),
        "gold_dist": gold_dist, "pred_dist": pred_dist,
        "na_total": na_total,
        "hard_wrong_na": [{"claim_id": r["claim_id"], "gold": r["gold"], "pred": r["pred"],
                          "probs": r["probs"]} for r in hard_wrong],
        "low_conf_right_na": [{"claim_id": r["claim_id"], "gold": r["gold"], "pred": r["pred"],
                              "probs": r["probs"]} for r in low_conf_right],
        "all_records": [{"claim_id": r["claim_id"], "gold": r["gold"], "pred": r["pred"],
                        "probs": r["probs"]} for r in rows],
    }
    out_path = OUTPUTS / "task3_train_self_eval_2026-09-22.json"
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n=== Train 自评结果 ===")
    print(f"gold 分布: {gold_dist}")
    print(f"pred 分布: {pred_dist}")
    print(f"NA 总数: {na_total}")
    print(f"A. 判错的 NA 样本: {len(hard_wrong)} 条")
    print(f"B. 判对但低置信(<{LOW_CONF})的 NA 样本: {len(low_conf_right)} 条")
    print(f"合计难样本: {len(hard_wrong) + len(low_conf_right)} 条")
    print("结果已存:", out_path)


if __name__ == "__main__":
    main()
