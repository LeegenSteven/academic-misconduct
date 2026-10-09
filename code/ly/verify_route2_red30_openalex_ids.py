import csv
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import requests

p = Path('_in_接口联调结果_v3(2).csv')
rows = list(csv.DictReader(p.open(encoding='utf-8-sig', newline='')))
red = [r for r in rows if r['dataset'] == 'RED']
pairs = {}
for r in red:
    pairs[r['citing_doi'].lower()] = r['citing_w']
    pairs[r['cited_doi'].lower()] = r['cited_w']

def check(item):
    doi, expected = item
    url = 'https://api.openalex.org/works/https://doi.org/' + quote(doi, safe='/')
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=15, headers={'User-Agent': 'route2-red-id-audit/1.0 (academic citation research)'})
            if resp.status_code == 200:
                actual = resp.json()['id'].rsplit('/', 1)[-1]
                return {'doi':doi,'expected':expected,'actual':actual,'status':200,'ok':actual==expected,'url':url}
            if resp.status_code in (429,500,502,503,504):
                time.sleep(1+attempt)
                continue
            return {'doi':doi,'expected':expected,'actual':'','status':resp.status_code,'ok':False,'url':url}
        except requests.RequestException as exc:
            if attempt == 2:
                return {'doi':doi,'expected':expected,'actual':'','status':type(exc).__name__,'ok':False,'url':url}
            time.sleep(1+attempt)
    return {'doi':doi,'expected':expected,'actual':'','status':'retry_exhausted','ok':False,'url':url}

results = []
with ThreadPoolExecutor(max_workers=4) as pool:
    futures = [pool.submit(check,item) for item in pairs.items()]
    for future in as_completed(futures):
        results.append(future.result())
results.sort(key=lambda r:r['doi'])
out = Path('results/ly/route2_interface_samples_v1/route2_red30_openalex_id_audit_2026-10-09.csv')
out.parent.mkdir(parents=True,exist_ok=True)
with out.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(results[0]))
    w.writeheader()
    w.writerows(results)
print(json.dumps({'unique_dois':len(pairs),'ok':sum(r['ok'] for r in results),'statuses':dict(Counter(str(r['status']) for r in results)),'failures':[r for r in results if not r['ok']]},ensure_ascii=False,indent=2))
