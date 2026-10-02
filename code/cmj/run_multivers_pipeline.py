# -*- coding: utf-8 -*-
"""
MultiVerS 分类管道冒烟测试（端到端第三段）
============================================
输入：BM25 检索 + MonoT5 重排得到的 top-k 证据句（monot5_30_eval_result.json）
模型：allenai/longformer-base-4096（本地权重）+ MultiVerS 官方分类头结构
      （Dropout + 2 层 MLP: hidden->hidden->3，激活 [GELU, Identity]）
标签映射（官方 predict.py decode 口径）：{0: NOT_ACCURATE, 1: NEI, 2: ACCURATE}

⚠️ 重要标注：
- 本脚本为【管道冒烟验证】：编码器用预训练 Longformer，分类头为随机初始化
  （未加载官方 scifact.ckpt / healthver.ckpt，因本机网络无法在可接受时间内
  获取该 4.89GB checkpoint）。输出概率与标签【无指标意义】，仅验证
  "claim+evidence -> tokenize -> Longformer 编码 -> 三分类输出" 的代码链路。
- 输入构造为句级简化版（claim + top-k 证据句），与官方"claim + 单个 abstract"
  的输入略有差异，已在结果中标注。
"""
import json
import sys
import time
import argparse
from pathlib import Path

import torch
from torch import nn
import torch.nn.functional as F
from transformers import LongformerTokenizerFast, LongformerModel

# ---------- 路径 ----------
WORK = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work")
OUTPUTS = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\outputs")
ENCODER_DIR = WORK / "longformer-base-4096"
CLAIMS_TEST = WORK / "converted-three-class" / "claims-test.jsonl"
MONOT5_RESULT = OUTPUTS / "monot5_30_eval_result.json"

LABEL_LOOKUP = {0: "NOT_ACCURATE", 1: "NEI", 2: "ACCURATE"}  # 官方 decode 口径


class RandomHead(nn.Module):
    """对齐官方 label_classifier（FeedForward 2 层）结构，随机初始化。"""

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


def load_claims(path):
    """读取 converted-three-class claims-test.jsonl，返回 id -> claim 文本。"""
    claims = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            claims[int(d["id"])] = d["claim"].replace("<|multi_cit|>", "").strip()
    return claims


def load_gold(path):
    """
    读取 evidence，构造句级 gold 映射：
    (claim_id, doc_id, sentence_index) -> label（三分类）
    """
    gold = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            cid = int(d["id"])
            for doc_id, evs in d.get("evidence", {}).items():
                for ev in evs:
                    for sidx in ev.get("sentences", []):
                        gold[(cid, int(doc_id), int(sidx))] = ev["label"]
    return gold


def build_inputs(claims, monot5_result, n_claims, top_k):
    """构造每条 claim 的输入：claim 文本 + top-k 证据句。"""
    inputs = []
    for item in monot5_result["results"][:n_claims]:
        cid = int(item["claim_id"])
        evs = []
        for ev in item["top10"][:top_k]:
            evs.append({
                "doc_id": ev["doc_id"],
                "sentence_index": ev["sentence_index"],
                "text": ev["text"],
            })
        inputs.append({"claim_id": cid, "claim": claims.get(cid, ""), "evidence": evs})
    return inputs


def tokenize_for_multivers(tokenizer, claim, evidence_sents):
    """
    官方 data.py 输入构造（简化）：
    claim </s> 证据句1 </s> 证据句2 </s> ...
    global_attention_mask：claim 部分 + 特殊 token = 1
    """
    # 特殊 token 定位（Longformer = RoBERTa 系：<s> / </s>）
    bos, eos = tokenizer.bos_token_id, tokenizer.eos_token_id
    parts = [claim]
    for s in evidence_sents:
        parts.append(s)
    text = tokenizer.eos_token.join(parts) + tokenizer.eos_token
    # 注意：transformers 4.57 的 LongformerTokenizerFast 传 truncation/max_length
    # 会触发 OverflowError，这里手动截断到 model_max_length。
    tokenized = tokenizer(text, padding=False, return_tensors="pt")
    input_ids = tokenized["input_ids"][0][: tokenizer.model_max_length]
    attention_mask = torch.ones_like(input_ids).unsqueeze(0)
    # global attention：<s>、所有 </s>、以及第一个 </s> 之前的 claim 部分
    is_special = (input_ids == bos) | (input_ids == eos)
    first_eos = (input_ids == eos).nonzero()[0][0].item()
    is_claim = torch.arange(len(input_ids)) < first_eos
    global_attention = (is_special | is_claim).to(torch.long).unsqueeze(0)
    tokenized = {"input_ids": input_ids.unsqueeze(0), "attention_mask": attention_mask,
                 "global_attention_mask": global_attention}
    return tokenized


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n_claims", type=int, default=10, help="冒烟测试的 claim 条数")
    ap.add_argument("--top_k", type=int, default=5, help="每条取 top-k 证据句")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    t0 = time.time()

    print(f"[1/5] 加载 Longformer-base-4096（本地）...", flush=True)
    tokenizer = LongformerTokenizerFast.from_pretrained(str(ENCODER_DIR))
    encoder = LongformerModel.from_pretrained(str(ENCODER_DIR))
    encoder.eval()
    head = RandomHead(encoder.config.hidden_size, 3, encoder.config.hidden_dropout_prob)
    head.eval()

    print(f"[2/5] 加载 claims 与 gold...", flush=True)
    claims = load_claims(CLAIMS_TEST)
    gold = load_gold(CLAIMS_TEST)
    print(f"      claims-test 共 {len(claims)} 条；evidence 句标注 {len(gold)} 条")

    print(f"[3/5] 读取 MonoT5 top-k 结果并构造输入...", flush=True)
    with open(MONOT5_RESULT, encoding="utf-8") as f:
        monot5 = json.load(f)
    inputs = build_inputs(claims, monot5, args.n_claims, args.top_k)
    print(f"      {len(inputs)} 条 claim，每条 top-{args.top_k} 证据句")

    print(f"[4/5] CPU 推理（随机分类头，管道冒烟）...", flush=True)
    results = []
    t_infer_start = time.time()
    with torch.no_grad():
        for i, inp in enumerate(inputs):
            ev_sents = [e["text"] for e in inp["evidence"]]
            tokenized = tokenize_for_multivers(tokenizer, inp["claim"], ev_sents)
            encoded = encoder(**tokenized)
            pooled = encoded.pooler_output
            logits = head(pooled)
            probs = F.softmax(logits, dim=1)[0]
            pred = int(logits.argmax(dim=1)[0])
            # 句级 gold（仅在 evidence 有标注时）
            gold_labels = []
            for e in inp["evidence"]:
                g = gold.get((inp["claim_id"], e["doc_id"], e["sentence_index"]))
                gold_labels.append(g if g else "UNLABELED")
            results.append({
                "claim_id": inp["claim_id"],
                "claim": inp["claim"][:120],
                "evidence": [
                    {"doc_id": e["doc_id"], "sentence_index": e["sentence_index"],
                     "gold": gl}
                    for e, gl in zip(inp["evidence"], gold_labels)
                ],
                "predicted_label": LABEL_LOOKUP[pred],
                "label_probs": {
                    LABEL_LOOKUP[k]: round(float(probs[k]), 4)
                    for k in range(3)
                },
            })
            if (i + 1) % 5 == 0 or i == len(inputs) - 1:
                print(f"      已完成 {i+1}/{len(inputs)}，"
                      f"累计 {time.time()-t_infer_start:.1f}s", flush=True)
    infer_elapsed = time.time() - t_infer_start

    print(f"[5/5] 保存结果...", flush=True)
    out = {
        "status": "completed",
        "official": False,
        "note": (
            "管道冒烟验证：编码器=allenai/longformer-base-4096 预训练权重，"
            "分类头=随机初始化（未加载官方 scifact/healthver checkpoint，"
            "本机网络无法在可接受时间获取 4.89GB 权重）。"
            "输入构造=claim + top-k 证据句（句级简化版，非官方 claim+abstract 级）。"
            "输出概率与标签无指标意义，仅验证代码链路。"
        ),
        "model": "allenai/longformer-base-4096 + random-init classifier head",
        "device": "cpu",
        "n_claims": len(inputs),
        "top_k": args.top_k,
        "label_lookup": LABEL_LOOKUP,
        "evidence_source": "monot5_30_eval_result.json (BM25 候选 + MonoT5 重排)",
        "total_elapsed_seconds": round(time.time() - t0, 2),
        "infer_elapsed_seconds": round(infer_elapsed, 2),
        "results": results,
    }
    out_path = OUTPUTS / "multivers_pipeline_smoke_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"结果已保存: {out_path}")
    print(f"总耗时 {out['total_elapsed_seconds']}s，其中推理 {infer_elapsed:.1f}s")
    # 预测分布
    dist = {}
    for r in results:
        dist[r["predicted_label"]] = dist.get(r["predicted_label"], 0) + 1
    print("预测标签分布:", dist)


if __name__ == "__main__":
    main()
