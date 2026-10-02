# -*- coding: utf-8 -*-
"""
任务3：歪曲类难样本过采样（2倍）
在 run_task4_finetune.py 基础上唯一改动：
  - 原始 2141 条样本构造完后，把 Train 自评挖出的 550 条难样本
    （hard_wrong_na 250 + low_conf_right_na 300）再复制 1 份加入训练集
  - 难样本总共出现 2 次（原 1 份 + 复制 1 份）
  - 其余训练数据与全部配置（MAX_LEN=384, FREEZE_LAYERS=12, LR=1e-5,
    BATCH=1, GRAD_ACCUM=8, 1 epoch）与 step2141 完全一致
红线：过采样样本只来自 Train，不碰 Dev/Test；不改权重初始化、不加类别加权、不改输出层
IRRELEVANT 与无证据样本处理方式：与原训练完全一致——
  - IRRELEVANT 样本本轮不重复（只重复 NA 难样本）
  - 无证据样本继续用 BM25 top-20 候选句输入，不额外处理
用法：python run_task3_oversample2x.py --full
"""
import json, math, re, sys, time, argparse
from collections import Counter
from pathlib import Path

import torch
from torch import nn
from torch.optim import AdamW
from transformers import LongformerTokenizerFast, LongformerModel

import pytorch_lightning.utilities.argparse as _pla
for _n in ["_gpus_arg_default", "_tpu_arg_default", "_get_gpus_arg_default"]:
    if not hasattr(_pla, _n):
        setattr(_pla, _n, lambda *a, **k: None)

WORK = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work")
OUTPUTS = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\outputs")
CKPT = WORK / "checkpoints" / "scifact.ckpt"
ENCODER_DIR = WORK / "longformer-large-4096"
V2_TRAIN = WORK / "converted-three-class-v2" / "claims-train.jsonl"
CORPUS = WORK / "Citation-Integrity-main" / "Data" / "multivers-format" / "corpus.jsonl"
SELF_EVAL = OUTPUTS / "task3_train_self_eval_2026-09-22.json"

LABEL2ID = {"NOT_ACCURATE": 0, "IRRELEVANT": 1, "ACCURATE": 2}
MAX_LEN = 384
AW = 512
LR = 1e-5
BATCH = 1
GRAD_ACCUM = 8
FREEZE_LAYERS = 12
CKPT_EVERY = 250
OVERSAMPLE_X = 2  # 难样本总共出现 2 次（原 1 + 复制 1）


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
    head = LabelHead(hidden, 3, encoder.config.hidden_dropout_prob)
    head_mapped = {k.replace("_linear_layers.0", "fc1").replace("_linear_layers.1", "fc2"): v
                   for k, v in head_sd.items()}
    head.load_state_dict(head_mapped)
    return tokenizer, encoder, head


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


def build_samples(claims, corpus, tokenizer, limit=None, k_bm25=20):
    samples = []
    for c in claims:
        cid = int(c["id"])
        gold_label = c["gold"]
        if gold_label not in LABEL2ID:
            continue
        label = LABEL2ID[gold_label]
        ev = c.get("evidence")
        if ev and isinstance(ev, dict):
            sents = []
            for doc_id, annos in ev.items():
                for a in annos:
                    for si in a.get("sentences", []):
                        abs_ = corpus.get(int(doc_id), [])
                        if si < len(abs_):
                            sents.append(abs_[si])
            if sents:
                ids = tokenizer(tokenizer.eos_token.join([c["claim"]] + sents) + tokenizer.eos_token,
                                add_special_tokens=False)["input_ids"][:MAX_LEN]
                samples.append((ids, label, cid, "gold"))
                continue
        cand = [(int(d), i, s) for d in c["cited_doc_ids"] for i, s in enumerate(corpus.get(int(d), []))]
        sents = []
        if cand:
            lex = bm25(toks(c["claim"]), [toks(x[2]) for x in cand])
            order = sorted(range(len(cand)), key=lambda i: lex[i], reverse=True)[:k_bm25]
            sents = [cand[i][2] for i in order]
        ids = tokenizer(tokenizer.eos_token.join([c["claim"]] + sents) + tokenizer.eos_token,
                        add_special_tokens=False)["input_ids"][:MAX_LEN]
        samples.append((ids, label, cid, "bm25"))
        if limit and len(samples) >= limit:
            break
    return samples


def collate(tokenizer, batch):
    ids_list = [x[0] for x in batch]
    labels = torch.tensor([x[1] for x in batch])
    max_len = max(len(x) for x in ids_list)
    max_len = min(((max_len + AW - 1) // AW) * AW, 4096)
    input_ids = torch.full((len(batch), max_len), tokenizer.pad_token_id, dtype=torch.long)
    attn = torch.zeros((len(batch), max_len), dtype=torch.long)
    for i, ids in enumerate(ids_list):
        n = min(len(ids), max_len)
        input_ids[i, :n] = torch.tensor(ids[:n])
        attn[i, :n] = 1
    is_special = (input_ids == tokenizer.bos_token_id) | (input_ids == tokenizer.eos_token_id)
    first_eos = (input_ids == tokenizer.eos_token_id).long()
    first_eos_idx = torch.argmax(first_eos, dim=1).unsqueeze(1)
    has_eos = first_eos.sum(dim=1) > 0
    arange = torch.arange(max_len).unsqueeze(0)
    is_claim = arange < first_eos_idx
    is_claim = is_claim & has_eos.unsqueeze(1)
    global_attention = ((is_special | is_claim) & (attn == 1)).to(torch.long)
    return {"input_ids": input_ids, "attention_mask": attn, "global_attention_mask": global_attention}, labels


def save_ckpt(encoder, head, step, path):
    torch.save({"encoder": encoder.state_dict(), "head": head.state_dict(),
                "step": step}, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    print("[1/5] 加载模型与数据...", flush=True)
    tokenizer, encoder, head = load_multivers()
    claims = [json.loads(x) for x in open(V2_TRAIN, encoding="utf-8") if x.strip()]
    corpus = {}
    for line in open(CORPUS, encoding="utf-8"):
        x = json.loads(line); corpus[int(x["doc_id"])] = x.get("abstract", [])
    print(f"      Train {len(claims)} 条", flush=True)

    # 读难样本清单
    se = json.load(open(SELF_EVAL, encoding="utf-8"))
    hard_ids = set(r["claim_id"] for r in se["hard_wrong_na"])
    low_ids = set(r["claim_id"] for r in se["low_conf_right_na"])
    oversample_ids = hard_ids | low_ids
    print(f"      难样本: 判错NA {len(hard_ids)} + 低置信NA {len(low_ids)} = {len(oversample_ids)}", flush=True)

    smoke = args.smoke or (not args.full)
    limit = 32 if smoke else None
    print("[2/5] 构造训练样本并过采样...", flush=True)
    samples = build_samples(claims, corpus, tokenizer, limit=limit)
    orig_n = len(samples)
    # 找难样本在 samples 里的位置，复制 (OVERSAMPLE_X - 1) 份
    added = 0
    if not smoke:
        oversample_samples = [s for s in samples if s[2] in oversample_ids]
        samples.extend(oversample_samples)  # 复制 1 份 = 总共 2 次
        added = len(oversample_samples)
    print(f"      原始 {orig_n} 条 + 过采样 {added} 条 = {len(samples)} 条", flush=True)
    print(f"      输入类型 {dict(Counter(s[3] for s in samples))}", flush=True)
    print(f"      标签 {dict(Counter(s[1] for s in samples))} (0=NA,1=IRR,2=ACC)", flush=True)

    # 保存过采样清单（可复现）
    manifest = {
        "task": "任务3：难样本过采样2倍",
        "oversample_x": OVERSAMPLE_X,
        "hard_wrong_na_ids": sorted(hard_ids),
        "low_conf_right_na_ids": sorted(low_ids),
        "original_samples": orig_n,
        "added_samples": added,
        "total_samples": len(samples),
        "config": {"MAX_LEN": MAX_LEN, "FREEZE_LAYERS": FREEZE_LAYERS, "LR": LR,
                   "BATCH": BATCH, "GRAD_ACCUM": GRAD_ACCUM, "epochs": 1},
        "irr_handling": "IRRELEVANT样本本轮不重复，与原训练一致",
        "no_evidence_handling": "无证据样本继续用BM25 top-20候选句，不额外处理",
    }
    manifest_path = OUTPUTS / "task3_oversample2x_manifest_2026-09-23.json"
    json.dump(manifest, open(manifest_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"      过采样清单已存 {manifest_path}", flush=True)

    print("[3/5] 训练（冻结前 12 层 + embeddings）...", flush=True)
    encoder.train(); head.train()
    for name, p in encoder.named_parameters():
        if name.startswith("encoder.layer."):
            idx = int(name.split(".")[2])
            if idx < FREEZE_LAYERS:
                p.requires_grad = False
        elif name.startswith("embeddings."):
            p.requires_grad = False
    params = [p for p in encoder.parameters() if p.requires_grad] + list(head.parameters())
    print(f"      可训练参数模块数 {sum(1 for p in params)}", flush=True)
    opt = AdamW(params, lr=LR, weight_decay=0.01)
    loss_fn = nn.CrossEntropyLoss()
    t0 = time.time()
    running_loss, n_seen, n_batches = 0.0, 0, 0
    opt.zero_grad()
    n = len(samples)
    for i in range(0, n, BATCH):
        batch = samples[i:i + BATCH]
        tok, labels = collate(tokenizer, batch)
        out = encoder(**tok)
        logits = head(out.pooler_output)
        loss = loss_fn(logits, labels) / GRAD_ACCUM
        loss.backward()
        running_loss += loss.item() * GRAD_ACCUM
        n_seen += len(batch); n_batches += 1
        if n_batches % GRAD_ACCUM == 0 or i + BATCH >= n:
            opt.step(); opt.zero_grad()
        if (i + BATCH) % 100 <= BATCH or i + BATCH >= n:
            avg = running_loss / n_seen
            spd = n_seen / (time.time() - t0)
            print(f"      {i+BATCH}/{n}  avg_loss {avg:.4f}  {spd:.3f} 条/s  墙钟 {time.time()-t0:.0f}s", flush=True)
            running_loss, n_seen = 0.0, 0
        if not smoke and (i + BATCH) % CKPT_EVERY <= BATCH:
            p = OUTPUTS / f"task3_oversample2x_ckpt_step{i+BATCH}.pt"
            save_ckpt(encoder, head, i + BATCH, p)
            print(f"      已存 {p}", flush=True)

    tag = "smoke" if smoke else "full"
    final = OUTPUTS / f"task3_oversample2x_{tag}_step{n}.pt"
    save_ckpt(encoder, head, n, final)
    print(f"[4/5] 完成，总耗时 {time.time()-t0:.0f}s，最终模型 {final}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
