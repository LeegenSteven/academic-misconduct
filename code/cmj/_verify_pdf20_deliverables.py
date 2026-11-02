"""PDF20点被引检索交付文件全面自检。"""
import json, csv, os, hashlib

OUT_DIR = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_PDF20点被引检索"
REQ_PATH = r"C:\Users\Administrator\AppData\Local\Temp\ly_pdf20_20261020\cited_retrieval_requests.jsonl"

def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return condition

print("=" * 60)
print("1. 文件存在性与编码")
print("=" * 60)
files_ok = True
for fn in ["cited_evidence_results.jsonl", "cited_evidence_summary_top3.csv",
           "retrieval_manifest.json", "被引端检索结果说明_陈明进_20261020.md"]:
    p = os.path.join(OUT_DIR, fn)
    exists = os.path.exists(p)
    if exists:
        size = os.path.getsize(p)
        with open(p, "rb") as f:
            head = f.read(3)
        bom = "UTF-8-BOM" if head == b"\xef\xbb\xbf" else "UTF-8"
        check(f"{fn}", size > 0, f"{size:,} bytes, {bom}")
    else:
        check(f"{fn}", False, "文件不存在")
        files_ok = False

print()
print("=" * 60)
print("2. JSONL 编码与乱码检查")
print("=" * 60)
jsonl_path = os.path.join(OUT_DIR, "cited_evidence_results.jsonl")
with open(jsonl_path, "r", encoding="utf-8") as f:
    lines = f.readlines()
check("总行数=20", len(lines) == 20, f"实际{len(lines)}")

bad_json = 0
replacement_chars = 0
for i, line in enumerate(lines):
    try:
        r = json.loads(line)
    except Exception:
        bad_json += 1
        print(f"    行{i+1} JSON解析失败")
        continue
    raw = json.dumps(r, ensure_ascii=False)
    if "\ufffd" in raw:
        replacement_chars += 1
        print(f"    行{i+1} 含U+FFFD乱码替换字符")
check("JSON全部可解析", bad_json == 0, f"失败{bad_json}行")
check("无乱码替换字符", replacement_chars == 0, f"含乱码{replacement_chars}行")

print()
print("=" * 60)
print("3. 字段完整性检查")
print("=" * 60)
results = [json.loads(l) for l in lines]
required_top = ["case_id", "pair_id", "target_reference_id", "cited_pmcid", "cited_title",
                "cited_pdf_sha256", "cited_pdf_relative_path", "query", "query_source",
                "status", "total_blocks", "candidates"]
required_cand = ["evidence_id", "rank", "bm25_score", "pdf_page", "block_number",
                 "char_start", "char_end_exclusive", "bbox", "raw_text",
                 "raw_text_sha256", "granularity"]
missing_top = 0
missing_cand = 0
for r in results:
    cid = r.get("case_id", "?")
    for k in required_top:
        if k not in r:
            missing_top += 1
            print(f"    {cid} 缺顶层字段: {k}")
    for c in r.get("candidates", []):
        eid = c.get("evidence_id", "?")
        for k in required_cand:
            if k not in c:
                missing_cand += 1
                print(f"    {cid}/{eid} 缺候选字段: {k}")
check("顶层字段完整", missing_top == 0, f"缺失{missing_top}")
check("候选字段完整", missing_cand == 0, f"缺失{missing_cand}")
check("每条10个候选", all(len(r["candidates"]) == 10 for r in results),
      f"实际{[len(r['candidates']) for r in results if len(r['candidates'])!=10]}")

print()
print("=" * 60)
print("4. case_id 与 cited_pmcid 对应检查")
print("=" * 60)
with open(REQ_PATH, "r", encoding="utf-8") as f:
    reqs = [json.loads(l) for l in f]
req_map = {r["case_id"]: r["cited_pdf"]["pmcid"] for r in reqs}
mismatch = 0
for r in results:
    cid = r["case_id"]
    expected = req_map.get(cid)
    actual = r["cited_pmcid"]
    if expected != actual:
        mismatch += 1
        print(f"    MISMATCH {cid}: expected={expected}, actual={actual}")
check("case_id/pmcid对应正确", mismatch == 0, f"错误{mismatch}条")
check("20个case_id唯一", len(set(r["case_id"] for r in results)) == 20)

print()
print("=" * 60)
print("5. 字符区间与页码合理性")
print("=" * 60)
bad_range = 0
bad_page = 0
for r in results:
    cid = r["case_id"]
    for c in r["candidates"]:
        cs, ce = c["char_start"], c["char_end_exclusive"]
        pg = c["pdf_page"]
        if cs is None or ce is None or cs >= ce:
            bad_range += 1
            print(f"    {cid}/{c['evidence_id']}: char_start={cs} >= char_end={ce}")
        if pg is None or pg < 1:
            bad_page += 1
            print(f"    {cid}/{c['evidence_id']}: pdf_page={pg}")
check("字符区间合理(char_start < char_end)", bad_range == 0, f"异常{bad_range}")
check("页码合理(>=1)", bad_page == 0, f"异常{bad_page}")

print()
print("=" * 60)
print("6. raw_text_sha256 一致性")
print("=" * 60)
hash_mismatch = 0
for r in results:
    for c in r["candidates"]:
        actual = hashlib.sha256(c["raw_text"].encode("utf-8")).hexdigest()
        if c["raw_text_sha256"] != actual:
            hash_mismatch += 1
            print(f"    {r['case_id']}/{c['evidence_id']}: hash不匹配")
check("raw_text哈希一致", hash_mismatch == 0, f"不匹配{hash_mismatch}")

print()
print("=" * 60)
print("7. bbox 格式检查")
print("=" * 60)
bad_bbox = 0
for r in results:
    for c in r["candidates"]:
        bbox = c["bbox"]
        if bbox is None or not isinstance(bbox, list) or len(bbox) != 4:
            bad_bbox += 1
check("bbox为4元素列表", bad_bbox == 0, f"异常{bad_bbox}")

print()
print("=" * 60)
print("8. CSV 文件检查")
print("=" * 60)
csv_path = os.path.join(OUT_DIR, "cited_evidence_summary_top3.csv")
with open(csv_path, "r", encoding="utf-8-sig") as f:
    reader = csv.reader(f)
    header = next(reader)
    rows = list(reader)
check("CSV表头列数=19", len(header) == 19, f"实际{len(header)}")
check("CSV行数=60(20点x3候选)", len(rows) == 60, f"实际{len(rows)}")
# 检查CSV中无乱码
csv_bad = sum(1 for row in rows for cell in row if "\ufffd" in cell)
check("CSV无乱码替换字符", csv_bad == 0, f"异常{csv_bad}")

print()
print("=" * 60)
print("9. manifest.json 检查")
print("=" * 60)
manifest_path = os.path.join(OUT_DIR, "retrieval_manifest.json")
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)
check("manifest含stats", "stats" in manifest)
check("stats.total=20", manifest.get("stats", {}).get("total") == 20)
check("stats.ok=18", manifest.get("stats", {}).get("ok") == 18,
      f"实际{manifest.get('stats',{}).get('ok')}")
check("stats.low_confidence=2", manifest.get("stats", {}).get("low_confidence") == 2,
      f"实际{manifest.get('stats',{}).get('low_confidence')}")
check("manifest含case_summary(20条)", len(manifest.get("case_summary", [])) == 20)

print()
print("=" * 60)
print("10. 说明文档引用准确性检查")
print("=" * 60)
md_path = os.path.join(OUT_DIR, "被引端检索结果说明_陈明进_20261020.md")
with open(md_path, "r", encoding="utf-8") as f:
    md = f.read()
check("说明文档含Case 3低置信度说明", "Case 3" in md and "Sliding Window" in md)
check("说明文档含Case 15低置信度说明", "Case 15" in md and "PDB" in md)
check("说明文档无乱码", "\ufffd" not in md)
# 检查说明文档中提到的case_id是否真实存在
check("说明文档中Case 3的case_id正确",
      "ecd1a395eb5f25610750d721" in md)
check("说明文档中Case 15的case_id正确",
      "896e930269210ee1300d8037" in md)

print()
print("=" * 60)
print("11. 检索结果内容抽查（top1原文是否与query相关）")
print("=" * 60)
# 抽查5个ok状态的case，确认top1原文与query有语义重叠
import re
def tokenize(t):
    return set(re.findall(r"[a-z0-9]+", t.lower()))
sample_indices = [0, 4, 7, 11, 16]
for idx in sample_indices:
    r = results[idx]
    q_tokens = tokenize(r["query"])
    e_tokens = tokenize(r["candidates"][0]["raw_text"])
    overlap = q_tokens & e_tokens
    # 过滤停用词
    stop = {"the","a","an","of","and","in","to","for","is","was","were","are","be","by","with","as","on","at","from","that","this","it","its","or","not","but","has","have","had","been","which","who","their","they","we","our","can","may","also","more","than","such","these","those","into","about","between","during","before","after","over","under","again","further","then","once","here","there","when","where","why","how","all","any","both","each","few","more","most","other","some","such","no","nor","only","own","same","so","too","very","just","because","if","while","although","however","therefore","thus","hence","indeed","still","yet","even","also","well","back","up","down","out","off","over","again","further","then","once"}
    content_overlap = overlap - stop
    status = "相关" if len(content_overlap) >= 2 else "可能不相关"
    print(f"    Case {idx+1} ({r['cited_pmcid']}): query与top1重叠词={len(content_overlap)}个 [{status}]")
    if len(content_overlap) < 2:
        print(f"      重叠词: {content_overlap}")
        print(f"      query: {r['query'][:100]}")
        print(f"      top1:  {r['candidates'][0]['raw_text'][:100]}")

print()
print("=" * 60)
print("自检完成")
print("=" * 60)
