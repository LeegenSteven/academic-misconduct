# -*- coding: utf-8 -*-
"""
任务2：生成60条证据定位核对表（从 Test 606 分层抽样）
每条列：claim_id / gold / pred / claim / 金标准证据句 / 模型BM25 top-1句 / 被引文献doc_id
人工核对列（留空）：
  loc_ok: 模型选句是否在原文对应位置(是/否)
  ev_ok: 证据是否适用(是/否/证据不适用)
  note: 一句话
分层：按 gold 分布抽（ACC 386/606≈38, NA 166≈16, IRR 52≈6），有金标准证据的优先
"""
import json, math, re, csv, random
from collections import Counter
from pathlib import Path

WORK = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work")
OUTPUTS = Path(r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\outputs")
V2_TEST = WORK / "converted-three-class-v2" / "claims-test.jsonl"
CORPUS = WORK / "Citation-Integrity-main" / "Data" / "multivers-format" / "corpus.jsonl"
TEST_RESULT = OUTPUTS / "task4_finetuned_test_eval_task4_finetuned_full_step2141_2026-09-22.json"
KB = 1

random.seed(42)  # 可复现抽样

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

# 读 Test 结果（pred）
test_res = json.load(open(TEST_RESULT, encoding="utf-8"))
pred_map = {r["claim_id"]: r["pred"] for r in test_res["results"]}

# 读 v2 test + corpus
claims = [json.loads(x) for x in open(V2_TEST, encoding="utf-8") if x.strip()]
corpus = {}
for line in open(CORPUS, encoding="utf-8"):
    x = json.loads(line); corpus[int(x["doc_id"])] = x.get("abstract", [])

# 给每条拼：金标准证据句 + 模型BM25 top-1句
def gold_sentences(c):
    evs = c.get("evidence", {}) or {}
    out = []
    for doc_id_str, groups in evs.items():
        doc_id = int(doc_id_str)
        sents = corpus.get(doc_id, [])
        for g in groups:
            for si in g.get("sentences", []):
                if 0 <= si < len(sents):
                    out.append((doc_id, si, sents[si]))
    return out

def model_top1(c):
    cand = [(int(d), i, s) for d in c["cited_doc_ids"] for i, s in enumerate(corpus.get(int(d), []))]
    if not cand: return None
    lex = bm25(toks(c["claim"]), [toks(x[2]) for x in cand])
    best = max(range(len(cand)), key=lambda i: lex[i])
    return cand[best]  # (doc_id, sent_idx, text)

rows = []
for c in claims:
    cid = int(c["id"])
    gs = gold_sentences(c)
    m1 = model_top1(c)
    rows.append({
        "claim_id": cid,
        "gold": c["gold"],
        "pred": pred_map.get(cid, "?"),
        "claim": c["claim"],
        "gold_ev": " || ".join(f"[d{d}#{i}] {s}" for d,i,s in gs),
        "model_ev": f"[d{m1[0]}#{m1[1]}] {m1[2]}" if m1 else "(无候选)",
        "has_gold": len(gs) > 0,
    })

# 分层抽样：ACC 38, NA 16, IRR 6，优先有金标准证据的
by_gold = {"ACCURATE": [], "NOT_ACCURATE": [], "IRRELEVANT": []}
for r in rows:
    by_gold[r["gold"]].append(r)
sample = []
for g, n in [("ACCURATE", 38), ("NOT_ACCURATE", 16), ("IRRELEVANT", 6)]:
    pool = by_gold[g]
    with_gold = [r for r in pool if r["has_gold"]]
    without_gold = [r for r in pool if not r["has_gold"]]
    random.shuffle(with_gold); random.shuffle(without_gold)
    take_gold = min(n, len(with_gold))
    sample.extend(with_gold[:take_gold])
    if take_gold < n:
        sample.extend(without_gold[:n - take_gold])
print(f"抽样: ACC {sum(1 for r in sample if r['gold']=='ACCURATE')}, "
      f"NA {sum(1 for r in sample if r['gold']=='NOT_ACCURATE')}, "
      f"IRR {sum(1 for r in sample if r['gold']=='IRRELEVANT')}, 共{len(sample)}")

# 输出 CSV（人工核对列留空）
out_path = OUTPUTS / "task2_evidence_location_check_60_2026-09-22.csv"
fields = ["claim_id", "gold", "pred", "claim", "gold_ev", "model_ev",
          "loc_ok(是/否)", "ev_ok(是/否/不适用)", "note"]
with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for i, r in enumerate(sample):
        w.writerow({"claim_id": r["claim_id"], "gold": r["gold"], "pred": r["pred"],
                    "claim": r["claim"], "gold_ev": r["gold_ev"], "model_ev": r["model_ev"],
                    "loc_ok(是/否)": "", "ev_ok(是/否/不适用)": "", "note": ""})
print("已生成:", out_path)
