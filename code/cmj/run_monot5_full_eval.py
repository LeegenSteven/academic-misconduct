# -*- coding: utf-8 -*-
"""MonoT5 全量重排：测试集 606 条 claim（BM25 粗选 top10 → MonoT5 精排 top10）"""
from __future__ import annotations
import json, math, re, time
from collections import Counter
from pathlib import Path
import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer

ROOT = Path(__file__).resolve().parents[0] / "Citation-Integrity-main" / "Data" / "multivers-format"
OUT = Path(__file__).resolve().parents[1] / "outputs" / "monot5_full_eval_result.json"
MODEL = str(Path(__file__).resolve().parents[0] / "hf_cache" / "hub" / "models--castorini--monot5-base-med-msmarco" / "snapshots" / "7a4324f2785ab5f1dea00e7a39d6f81f3e2d273f")

def toks(s): return re.findall(r"[A-Za-z0-9]+", s.lower())
def bm25(q, docs):
    n=len(docs); avg=sum(map(len,docs))/max(n,1); dfs=Counter(t for d in docs for t in set(d)); out=[]
    for d in docs:
        tf=Counter(d); z=0.0
        for t in q:
            if t not in tf: continue
            idf=math.log(1+(n-dfs[t]+.5)/(dfs[t]+.5)); den=tf[t]+1.5*(.25+.75*len(d)/max(avg,1))
            z += idf*tf[t]*2.5/den
        out.append(z)
    return out

def main():
    claims=[json.loads(x) for x in (ROOT/'claims-test.jsonl').open(encoding='utf-8') if x.strip()]
    corpus={}
    for line in (ROOT/'corpus.jsonl').open(encoding='utf-8'):
        x=json.loads(line); corpus[int(x['doc_id'])]=x.get('abstract',[])
    tokenizer=T5Tokenizer.from_pretrained(MODEL,use_fast=False,local_files_only=True)
    model=T5ForConditionalGeneration.from_pretrained(MODEL,local_files_only=True); model.eval()
    true_id=tokenizer('true',add_special_tokens=False).input_ids[0]; false_id=tokenizer('false',add_special_tokens=False).input_ids[0]
    results=[]; start=time.time(); total_gold=0; rank1_hits=0; rank5_hits=0; rank10_hits=0
    for ci,claim in enumerate(claims,1):
        gold={(int(d),int(s)) for d,es in claim.get('evidence',{}).items() for e in es for s in e.get('sentences',[])}
        total_gold += len(gold)
        cand=[(int(d),i,s) for d in claim['cited_doc_ids'] for i,s in enumerate(corpus.get(int(d),[]))]
        if not cand:
            results.append({'claim_id':claim['id'],'gold_count':len(gold),'bm25_candidate_count':0,'top10':[]})
            continue
        lex=bm25(toks(claim['claim']),[toks(x[2]) for x in cand]); order=sorted(range(len(cand)),key=lambda i:lex[i],reverse=True)[:10]
        prompts=[f"Query: {claim['claim']} Document: {cand[i][2]} Relevant:" for i in order]
        scores=[]
        for j in range(0,len(prompts),8):
            inp=tokenizer(prompts[j:j+8],return_tensors='pt',padding=True,truncation=True,max_length=512)
            with torch.no_grad():
                logits=model(**inp,decoder_input_ids=torch.full((len(prompts[j:j+8]),1),model.config.decoder_start_token_id,dtype=torch.long)).logits[:,-1,:]
            lp=torch.log_softmax(logits[:,[true_id,false_id]],dim=-1)[:,0].tolist(); scores.extend(lp)
        ranked=sorted(range(len(order)),key=lambda j:scores[j],reverse=True)
        top=[]
        for r,j in enumerate(ranked,1):
            d,si,text=cand[order[j]]; hit=(d,si) in gold
            top.append({'rank':r,'doc_id':d,'sentence_index':si,'true_logprob':scores[j],'is_gold':hit,'text':text})
            if hit and r==1: rank1_hits+=1
            if hit and r<=5: rank5_hits+=1
            if hit: rank10_hits+=1
        results.append({'claim_id':claim['id'],'gold_count':len(gold),'bm25_candidate_count':len(cand),'top10':top})
        if ci % 60 == 0 or ci==len(claims):
            print(f'{ci}/{len(claims)} done; rank1_gold={rank1_hits}; elapsed={time.time()-start:.0f}s',flush=True)
    out={'status':'completed','official':False,'model':'castorini/monot5-base-med-msmarco','device':'cpu','claims':len(claims),
         'rank1_gold_claims':rank1_hits,'rank1_gold_rate':round(rank1_hits/len(claims),4),
         'rank5_gold_claims':rank5_hits,'rank5_gold_rate':round(rank5_hits/len(claims),4),
         'gold_evidence_total':total_gold,'elapsed_seconds':round(time.time()-start,2),'results':results}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k!='results'},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
