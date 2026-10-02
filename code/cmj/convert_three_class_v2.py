# -*- coding: utf-8 -*-
"""任务1-转换 v2（修正版）：基于 converted-three-class 的三分类 evidence 判定有证据样本
规则（已冻结）：
- gold 三分类：ACCURATE / NOT_ACCURATE / IRRELEVANT
- 有 evidence：以 converted 三分类 evidence 为准，任一 NOT_ACCURATE -> NOT_ACCURATE，否则 ACCURATE
  （converted 规则：原始 ACCURATE/INDIRECT->ACCURATE，NOT_SUBSTANTIATE/MISQUOTE/CONTRADICT/OVERSIMPLIFY/ETIQUETTE->NOT_ACCURATE）
- 无 evidence：按原始标注映射（ETIQUETTE->NOT_ACCURATE, IRRELEVANT->IRRELEVANT,
  ACCURATE/INDIRECT/INDIRECT_NOT_REVIEW->ACCURATE, NOT_SUBSTANTIATE/CONTRADICT/OVERSIMPLIFY/MISQUOTE->NOT_ACCURATE）
  并加 evidence_missing=True
"""
import zipfile, json, re, os
from collections import Counter

CV = r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work\converted-three-class"
MF = r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work\Citation-Integrity-main\Data\multivers-format"
ANN = r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work\Citation-Integrity-main\Data\annotations.zip"
OUT = r"C:\Users\Administrator\Documents\Codex\2026-08-30\jie\work\converted-three-class-v2"
os.makedirs(OUT, exist_ok=True)

z = zipfile.ZipFile(ANN)

def norm(s):
    return re.sub(r"\s+", " ", s.replace("[<|cit|>]", "M").replace("[<|multi_cit|>]", "M")).strip().lower()

MAP = {
    "ETIQUETTE": "NOT_ACCURATE",
    "IRRELEVANT": "IRRELEVANT",
    "ACCURATE": "ACCURATE",
    "INDIRECT": "ACCURATE",
    "INDIRECT_NOT_REVIEW": "ACCURATE",
    "NOT_SUBSTANTIATE": "NOT_ACCURATE",
    "CONTRADICT": "NOT_ACCURATE",
    "OVERSIMPLIFY": "NOT_ACCURATE",
    "MISQUOTE": "NOT_ACCURATE",
}

def load_ann(split):
    cits = [n for n in z.namelist() if f"/{split}/citations/" in n and n.endswith(".json") and "__MACOSX" not in n]
    ann = {}
    for a in cits:
        d = json.loads(z.read(a))
        ctx = (d.get("citation_context") or [{}])[0].get("text", "")
        ann.setdefault(norm(ctx), []).append(d.get("label"))
    return ann

def gold_from_converted_evidence(evidence):
    for doc_id, evs in (evidence or {}).items():
        for e in evs:
            if e.get("label") == "NOT_ACCURATE":
                return "NOT_ACCURATE"
    return "ACCURATE"

for split in ("Train", "Dev", "Test"):
    mf = [json.loads(l) for l in open(os.path.join(MF, f"claims-{split.lower()}.jsonl"), encoding="utf-8") if l.strip()]
    cv = {str(c["id"]): c for c in (json.loads(l) for l in open(os.path.join(CV, f"claims-{split.lower()}.jsonl"), encoding="utf-8") if l.strip())}
    ann = load_ann(split)
    out_lines, cnt = [], Counter()
    unknown, mism = [], 0
    for c in mf:
        mf_ev = c.get("evidence") or {}
        if mf_ev:
            mf_labels = {e.get("label") for evs in mf_ev.values() for e in evs}
            if mf_labels == {"IRRELEVANT"}:
                # 有 evidence 但全部标 IRRELEVANT：归 IRRELEVANT，保留 evidence，不加 evidence_missing
                gold = "IRRELEVANT"
                rec = {"id": str(c["id"]), "claim": c["claim"], "evidence": mf_ev,
                       "cited_doc_ids": c.get("cited_doc_ids", []), "gold": gold}
            else:
                cv_rec = cv.get(str(c["id"]))
                ev = (cv_rec or {}).get("evidence") or mf_ev
                gold = gold_from_converted_evidence(ev)
                rec = {"id": str(c["id"]), "claim": c["claim"], "evidence": ev,
                       "cited_doc_ids": c.get("cited_doc_ids", []), "gold": gold}
                if (cv_rec or {}).get("gold") and gold != cv_rec.get("gold"):
                    mism += 1
        else:
            key = norm(c["claim"])
            raw = None
            for ctx, labs in ann.items():
                if ctx and (ctx == key or ctx in key):
                    raw = labs[0]
                    break
            if raw is None:
                unknown.append(c["id"])
                raw = "ETIQUETTE"
            gold = MAP.get(raw, "NOT_ACCURATE")
            rec = {"id": str(c["id"]), "claim": c["claim"], "evidence": {},
                   "cited_doc_ids": c.get("cited_doc_ids", []), "gold": gold,
                   "evidence_missing": True}
        cnt[gold] += 1
        out_lines.append(json.dumps(rec, ensure_ascii=False))
    out_path = os.path.join(OUT, f"claims-{split.lower()}.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    print(f"=== {split}: {len(mf)}条 -> {out_path}")
    print(f"    gold 分布: {dict(cnt)} | 无evidence未匹配: {len(unknown)} {unknown[:10]} | 有证据与converted旧gold不一致: {mism}")
