"""Validate the published Sarol training files; standard library only."""
import hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"data/quality_v1/sarol"
def rows(name):
 return [json.loads(s) for s in (p/name).read_text(encoding="utf-8-sig").splitlines() if s.strip()]
m=json.loads((p/"training_manifest.json").read_text(encoding="utf-8"))
for name,digest in m["files"].items():
 if hashlib.sha256((p/name).read_bytes()).hexdigest()!=digest:raise ValueError("hash mismatch: "+name)
c={str(r["doc_id"]):r for r in rows("corpus.jsonl")}
if len(c)!=8515:raise ValueError("corpus count")
checked=0
for split,n in m["counts"].items():
 r=rows("claims-"+split+"-model.jsonl")
 if len(r)!=n or len({x["id"] for x in r})!=n:raise ValueError(split+": count/IDs")
 for x in r:
  if x["gold"] not in {"ACCURATE","NOT_ACCURATE","IRRELEVANT"}:raise ValueError("invalid gold")
  for d,es in x["evidence"].items():
   for e in es:
    for i in e["sentences"]:
     if d not in c or not 0<=i<len(c[d]["abstract"]):raise ValueError("invalid evidence")
     checked+=1
print(json.dumps({"validation":"passed","counts":m["counts"],"corpus_blocks":len(c),"evidence_sentence_references":checked},ensure_ascii=False))
