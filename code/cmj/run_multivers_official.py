# -*- coding: utf-8 -*-
"""
MultiVerS 官方权重推理（scifact.ckpt，CPU）
==========================================
加载官方 S3 下载的 scifact.ckpt（MultiVerS 在 SciFact 上训练的模型），
对 Sarol 测试集 claim 的 top-k 证据句做三分类。

标签映射（官方 model.py decode 口径）：{0: NOT_ACCURATE, 1: NEI, 2: ACCURATE}
模型结构（官方 model.py）：
  encoder（Longformer-large-4096，词表 50275）→ dropout → label_classifier
  label_classifier = FeedForward(2层): Linear(1024->1024)+GELU+Dropout → Linear(1024->3)
"""
import json
import time
import argparse
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn
from transformers import LongformerTokenizerFast, LongformerModel

# 旧版 pytorch-lightning pickle 兼容
import pytorch_lightning.utilities.argparse as _pla
for _n in ["_gpus_arg_default", "_tpu_arg_default", "_get_gpus_arg_default"]:
    if not hasattr(_pla, _n):
        setattr(_pla, _n, lambda *a, **k: None)

WORK = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work")
OUTPUTS = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\outputs")
CKPT = WORK / "checkpoints" / "scifact.ckpt"
ENCODER_DIR = WORK / "longformer-large-4096"
CLAIMS_TEST = WORK / "converted-three-class" / "claims-test.jsonl"
MONOT5_RESULT = OUTPUTS / "monot5_30_eval_result.json"

LABEL_LOOKUP = {0: "NOT_ACCURATE", 1: "NEI", 2: "ACCURATE"}


class LabelHead(nn.Module):
    """官方 label_classifier（FeedForward 2 层）+ dropout 结构。"""

    def __init__(self, hidden_size, num_labels, dropout_p):
        super().__init__()
        self.fc1 = nn.Linear(hidden_size, hidden_size)
        self.act = nn.GELU()
        self.dropout = nn.Dropout(dropout_p)
        self.fc2 = nn.Linear(hidden_size, num_labels)

    def forward(self, pooled):
        h = self.act(self.fc1(pooled))
        h = self.dropout(h)
        return self.fc2(h)


def load_checkpoint(ckpt_path):
    d = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    sd = d["state_dict"]
    enc_sd = {k[len("encoder."):]: v for k, v in sd.items() if k.startswith("encoder.")}
    head_sd = {k[len("label_classifier."):]: v for k, v in sd.items() if k.startswith("label_classifier.")}
    return enc_sd, head_sd, d.get("hyper_parameters", {})


def load_claims(path):
    claims = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            dd = json.loads(line)
            claims[int(dd["id"])] = dd["claim"].replace("<|multi_cit|>", "").strip()
    return claims


def load_gold(path):
    gold = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            dd = json.loads(line)
            cid = int(dd["id"])
            for doc_id, evs in dd.get("evidence", {}).items():
                for ev in evs:
                    for sidx in ev.get("sentences", []):
                        gold[(cid, int(doc_id), int(sidx))] = ev["label"]
    return gold


def tokenize_for_multivers(tokenizer, claim, evidence_sents):
    bos, eos = tokenizer.bos_token_id, tokenizer.eos_token_id
    parts = [claim] + list(evidence_sents)
    text = tokenizer.eos_token.join(parts) + tokenizer.eos_token
    tokenized = tokenizer(text, padding=False, return_tensors="pt")
    input_ids = tokenized["input_ids"][0][: tokenizer.model_max_length]
    attention_mask = torch.ones_like(input_ids).unsqueeze(0)
    is_special = (input_ids == bos) | (input_ids == eos)
    first_eos = (input_ids == eos).nonzero()[0][0].item()
    is_claim = torch.arange(len(input_ids)) < first_eos
    global_attention = (is_special | is_claim).to(torch.long).unsqueeze(0)
    return {"input_ids": input_ids.unsqueeze(0), "attention_mask": attention_mask,
            "global_attention_mask": global_attention}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n_claims", type=int, default=10)
    ap.add_argument("--top_k", type=int, default=5)
    ap.add_argument("--out", type=str, default="multivers_official_result.json")
    ap.add_argument("--evidence_file", type=str, default=None,
                    help="MonoT5 证据 json 路径（默认 monot5_30_eval_result.json）")
    args = ap.parse_args()

    t0 = time.time()
    print("[1/6] 加载官方 checkpoint 权重...", flush=True)
    enc_sd, head_sd, hp = load_checkpoint(CKPT)
    vocab_size = enc_sd["embeddings.word_embeddings.weight"].shape[0]
    hidden = enc_sd["embeddings.word_embeddings.weight"].shape[1]
    print(f"      词表 {vocab_size}，hidden {hidden}；head 参数 {len(head_sd)} 个", flush=True)

    print("[2/6] 加载 Longformer-large-4096 编码器骨架...", flush=True)
    tokenizer = LongformerTokenizerFast.from_pretrained(str(ENCODER_DIR))
    encoder = LongformerModel.from_pretrained(str(ENCODER_DIR))
    # 对齐官方词表大小并加载权重
    if encoder.config.vocab_size != vocab_size:
        encoder.resize_token_embeddings(vocab_size)
    encoder.load_state_dict(enc_sd, strict=False)  # position_ids 等 buffer 差异可忽略
    encoder.eval()

    print("[3/6] 构建官方分类头并加载权重...", flush=True)
    dropout_p = encoder.config.hidden_dropout_prob
    head = LabelHead(hidden, 3, dropout_p)
    # 官方 FeedForward key（_linear_layers.N.*）→ 本脚本 LabelHead key（fcN.*）
    head_mapped = {
        k.replace("_linear_layers.0", "fc1").replace("_linear_layers.1", "fc2"): v
        for k, v in head_sd.items()
    }
    head.load_state_dict(head_mapped)
    head.eval()

    print("[4/6] 加载 claims 与 gold...", flush=True)
    claims = load_claims(CLAIMS_TEST)
    gold = load_gold(CLAIMS_TEST)
    ev_path = Path(args.evidence_file) if args.evidence_file else MONOT5_RESULT
    with open(ev_path, encoding="utf-8") as f:
        monot5 = json.load(f)
    inputs = []
    for item in monot5["results"][: args.n_claims]:
        cid = int(item["claim_id"])
        evs = [{"doc_id": e["doc_id"], "sentence_index": e["sentence_index"], "text": e["text"]}
               for e in item["top10"][: args.top_k]]
        inputs.append({"claim_id": cid, "claim": claims.get(cid, ""), "evidence": evs})
    print(f"      {len(inputs)} 条 claim × top-{args.top_k}", flush=True)

    print("[5/6] CPU 推理（官方权重）...", flush=True)
    results = []
    t_infer = time.time()
    with torch.no_grad():
        for i, inp in enumerate(inputs):
            t_one = time.time()
            tokenized = tokenize_for_multivers(tokenizer, inp["claim"], [e["text"] for e in inp["evidence"]])
            encoded = encoder(**tokenized)
            pooled = encoder.dropout(encoded.pooler_output) if hasattr(encoder, "dropout") else encoded.pooler_output
            logits = head(pooled)
            probs = F.softmax(logits, dim=1)[0]
            pred = int(logits.argmax(dim=1)[0])
            gold_labels = [gold.get((inp["claim_id"], e["doc_id"], e["sentence_index"]), "UNLABELED")
                           for e in inp["evidence"]]
            results.append({
                "claim_id": inp["claim_id"],
                "claim": inp["claim"][:120],
                "evidence": [{"doc_id": e["doc_id"], "sentence_index": e["sentence_index"], "gold": gl}
                             for e, gl in zip(inp["evidence"], gold_labels)],
                "predicted_label": LABEL_LOOKUP[pred],
                "label_probs": {LABEL_LOOKUP[k]: round(float(probs[k]), 4) for k in range(3)},
            })
            print(f"      {i+1}/{len(inputs)} claim {inp['claim_id']} -> {LABEL_LOOKUP[pred]} "
                  f"({time.time()-t_one:.1f}s)", flush=True)
    infer_elapsed = time.time() - t_infer

    print("[6/6] 保存结果...", flush=True)
    out = {
        "status": "completed",
        "official": True,
        "checkpoint": str(CKPT),
        "checkpoint_source": "S3 scifact.s3.us-west-2.amazonaws.com/longchecker/latest/checkpoints/scifact.ckpt",
        "checkpoint_bytes": CKPT.stat().st_size,
        "model": "MultiVerS (Longformer-large-4096) 官方 SciFact checkpoint",
        "label_lookup": LABEL_LOOKUP,
        "evidence_source": "monot5 输出 top-k（BM25 候选 + MonoT5 重排）",
        "device": "cpu",
        "n_claims": len(inputs),
        "top_k": args.top_k,
        "total_elapsed_seconds": round(time.time() - t0, 2),
        "infer_elapsed_seconds": round(infer_elapsed, 2),
        "results": results,
    }
    out_path = OUTPUTS / args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"结果已保存: {out_path}", flush=True)
    dist = {}
    for r in results:
        dist[r["predicted_label"]] = dist.get(r["predicted_label"], 0) + 1
    print("预测分布:", dist, flush=True)
    print(f"总耗时 {out['total_elapsed_seconds']}s，推理 {infer_elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
