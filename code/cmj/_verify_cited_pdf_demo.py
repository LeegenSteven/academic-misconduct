# -*- coding: utf-8 -*-
"""独立验证 cited_pdf_demo：不经过生成逻辑，从落盘文件回读核验。"""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(r'C:\Users\Administrator\Documents\academic-misconduct')
OUT = REPO / 'results/cmj/cited_pdf_retrieval_v1_2026-10-18'
XML_DIR = REPO / 'data/raw/pmc_oa_v3_source_xml'

# 载入冻结 v2 的常量做口径比对
spec = importlib.util.spec_from_file_location('b', REPO / 'code/ly/build_sarol_inputs_v2.py')
v2 = importlib.util.module_from_spec(spec); sys.modules['b'] = v2; spec.loader.exec_module(v2)
# 载入 data_contract
sys.path.insert(0, str(REPO / 'code'))
from shared.route1_qwen38.data_contract import parse_label  # noqa

inputs = [json.loads(l) for l in open(OUT / 'cited_pdf_demo.inputs.jsonl', encoding='utf-8') if l.strip()]
locators = [json.loads(l) for l in open(OUT / 'cited_pdf_demo.locators.jsonl', encoding='utf-8') if l.strip()]
manifest = json.load(open(OUT / 'cited_pdf_demo.manifest.json', encoding='utf-8'))

fail = []
def check(cond, msg):
    print(('PASS' if cond else 'FAIL') + ' | ' + msg)
    if not cond:
        fail.append(msg)

check(len(inputs) == 2 and len(locators) == 2, '输入与定位各 2 条')
check(manifest['system_prompt_sha256'] == hashlib.sha256(v2.SYSTEM_PROMPT.encode('utf-8')).hexdigest(),
      'system_prompt 与冻结 v2 完全一致')

for inp, loc in zip(inputs, locators):
    cid = inp['claim_id']
    # 1. 字段完整性
    check(inp['system_prompt'] == v2.SYSTEM_PROMPT, f'{cid} system_prompt 一致')
    check(isinstance(inp['user_prompt'], str) and inp['user_prompt'].startswith('引用论断：'),
          f'{cid} user_prompt 以引用论断开头')
    # 2. 重算 input_sha256
    visible = {'system_prompt': inp['system_prompt'], 'user_prompt': inp['user_prompt']}
    recompute = hashlib.sha256(json.dumps(visible, ensure_ascii=False, sort_keys=True,
                                          separators=(',', ':')).encode('utf-8')).hexdigest()
    check(recompute == inp['input_sha256'], f'{cid} input_sha256 重算一致')
    # 3. evidence_id 格式与数量
    ids = inp['allowed_evidence_ids']
    check(len(ids) == 10 and len(set(ids)) == 10, f'{cid} 10 个唯一 evidence_id')
    check(all(re.fullmatch(r'D\d{2}:S\d{2}', x) for x in ids), f'{cid} evidence_id 全部 Dxx:Sxx')
    # 4. user_prompt 中的证据行与 candidate_evidence 一致
    lines = inp['user_prompt'].split('\n')
    ev_lines = [ln for ln in lines if re.match(r'D\d{2}:S\d{2} \| ', ln)]
    check(len(ev_lines) == 10, f'{cid} user_prompt 含 10 行候选证据')
    for ev, cand in zip(ev_lines, inp['candidate_evidence']):
        check(ev == f"{cand['evidence_id']} | {cand['text']}", f'{cid} {cand["evidence_id"]} 证据行与candidate一致')
    # 5. 定位与候选文本一致，且能在源 XML 段落中找到
    check(len(loc['evidence_locators']) == 10, f'{cid} 定位 10 条')
    import xml.etree.ElementTree as ET
    root = ET.parse(XML_DIR / f"{loc['cited_pmcid']}.xml").getroot()
    # 与生成端一致用空字符串 join（xref 编号 [145] 不被插入空格），再归一化空白
    fulltext_norm = re.sub(r'\s+', ' ', ''.join(root.itertext()))
    for e in loc['evidence_locators']:
        cand = next(c for c in inp['candidate_evidence'] if c['evidence_id'] == e['evidence_id'])
        check(e['text'] == cand['text'], f'{cid} {e["evidence_id"]} 定位文本与候选一致')
        check(e['text'] in fulltext_norm,
              f'{cid} {e["evidence_id"]} 定位文本可在源 XML 找到')
    # 6. 被引 XML 哈希
    h = hashlib.sha256((XML_DIR / f"{loc['cited_pmcid']}.xml").read_bytes()).hexdigest()
    check(h == loc['cited_xml_sha256'], f'{cid} 被引 XML SHA256 一致')
    # 7. claim 不含残留标记
    check('<CITED:' not in loc['claim'] and '<OTHER_CITATION:' not in loc['claim'],
          f'{cid} claim 已清理引用标记')

print('\n' + ('全部通过' if not fail else f'{len(fail)} 项失败'))
sys.exit(1 if fail else 0)
