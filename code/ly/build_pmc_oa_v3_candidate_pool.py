"""Build a traceable 10-record PMC natural-citation candidate pool.

This script uses the original citing-article XML and marks the exact bibliography
cross-reference inside the complete paragraph. It deliberately leaves both
annotator fields blank: this is a candidate/independent-review package, not a
final adjudicated trial set.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import requests


ROOT = Path(__file__).resolve().parents[3]
REPO = ROOT / ".repo_upload"
OUT_DATA = REPO / "data" / "interim"
OUT_RESULT = REPO / "results" / "ly" / "task3_natural_trial"
RAW = REPO / "data" / "raw" / "pmc_oa_v3_source_xml"
TMP = OUT_DATA / "pmc_oa_candidate_source_rows_ly_v3_2026-10-05.json"

SELECTED = [
    ("PMC12900525", "PMC10045528", "B1"),
    ("PMC12900525", "PMC10765876", "B3"),
    ("PMC12900525", "PMC4868912", "B15"),
    ("PMC12900525", "PMC4841349", "B29"),
    ("PMC13583542", "PMC13324970", "rcm70182-bib-0028"),
    ("PMC13583542", "PMC8876357", "rcm70182-bib-0056"),
    ("PMC13583542", "PMC13193722", "rcm70182-bib-0070"),
    ("PMC13625197", "PMC9708575", "glia70233-bib-0016"),
    ("PMC13625197", "PMC7504301", "glia70233-bib-0043"),
    ("PMC13625197", "PMC10464498", "glia70233-bib-0030"),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def strip_tags(root: ET.Element) -> None:
    for e in root.iter():
        if "}" in e.tag:
            e.tag = e.tag.rsplit("}", 1)[1]


def article_title(root: ET.Element) -> str:
    node = root.find(".//title-group/article-title")
    if node is None:
        node = root.find(".//article-title")
    return clean_text("".join(node.itertext())) if node is not None else ""


def article_doi(root: ET.Element) -> str:
    for node in root.findall(".//article-id"):
        if node.get("pub-id-type") == "doi":
            value = clean_text("".join(node.itertext()))
            if value:
                return value
    return ""


def license_url(root: ET.Element) -> str:
    for node in root.findall(".//license"):
        for child in node.iter():
            if child.tag.endswith("license_ref"):
                value = clean_text("".join(child.itertext()))
                if value:
                    return value
        text = clean_text("".join(node.itertext()))
        m = re.search(r"https?://[^\s]+", text)
        if m:
            return m.group(0).rstrip(".,)")
    return ""


def marked_text(node: ET.Element, target_rid: str, cited_pmcid: str) -> str:
    """Serialize a node while marking all bibliography xrefs explicitly."""
    chunks: list[str] = []
    if node.text:
        chunks.append(node.text)
    for child in list(node):
        if child.tag == "xref" and child.get("ref-type") == "bibr":
            rid = child.get("rid", "")
            ref_text = clean_text("".join(child.itertext()))
            if rid == target_rid:
                chunks.append(f"<CITED:{cited_pmcid}|{ref_text}>")
            else:
                chunks.append(f"<OTHER_CITATION:{rid}|{ref_text}>")
        else:
            chunks.append(marked_text(child, target_rid, cited_pmcid))
        if child.tail:
            chunks.append(child.tail)
    return "".join(chunks)


def find_marked_paragraph(root: ET.Element, target_rid: str, cited_pmcid: str) -> str:
    for p in root.iter("p"):
        if any(x is not None and x.get("rid") == target_rid for x in p.iter("xref")):
            return clean_text(marked_text(p, target_rid, cited_pmcid))
    raise ValueError(f"target bibliography xref not found: {target_rid}")


def abstract_text(root: ET.Element) -> str:
    parts: list[str] = []
    for abstract in root.findall(".//abstract"):
        text = clean_text(" ".join("".join(p.itertext()) for p in abstract.findall(".//p")))
        if not text:
            text = clean_text("".join(abstract.itertext()))
        if text and text not in parts:
            parts.append(text)
    return " ".join(parts)


def fetch_xml(pmcid: str) -> tuple[bytes, ET.Element]:
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    data = response.content
    root = ET.fromstring(data)
    strip_tags(root)
    return data, root


def load_existing_ids() -> tuple[set[str], set[str]]:
    cited: set[str] = set()
    citing: set[str] = set()
    for path in [
        OUT_DATA / "pmc_oa_candidate_pool_ly_v1_2026-10-03.json",
        OUT_DATA / "pmc_oa_candidate_pool_ly_v2_2026-10-03.json",
    ]:
        if path.exists():
            obj = json.loads(path.read_text(encoding="utf-8"))
            for rec in obj.get("records", []):
                if rec.get("cited_pmcid"):
                    cited.add(rec["cited_pmcid"])
                if rec.get("citing_pmcid"):
                    citing.add(rec["citing_pmcid"])
    final = OUT_RESULT / "pmc_oa_v2_final_trial_set_v3_2026-10-04.xlsx"
    # The final workbook is intentionally not parsed here; all its PMCID values
    # are already represented in the v2 candidate pool. The v2 pool remains the
    # authoritative exclusion list for this candidate-only build.
    return cited, citing


def main() -> None:
    source_rows = json.loads(TMP.read_text(encoding="utf-8"))
    source_by_key = {(r["citing_pmcid"], r["cited_pmcid"], r["rid"]): r for r in source_rows}
    existing_cited, existing_citing = load_existing_ids()

    # The selected IDs are deliberately new relative to v1/v2 candidates.
    for citing, cited, rid in SELECTED:
        if cited in existing_cited or citing in existing_citing:
            raise RuntimeError(f"selected source overlaps existing v1/v2 candidate: {citing}, {cited}")
        if (citing, cited, rid) not in source_by_key:
            raise RuntimeError(f"missing candidate source row: {citing}, {cited}, {rid}")

    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_RESULT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)

    cache: dict[str, tuple[bytes, ET.Element]] = {}
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    records: list[dict[str, Any]] = []
    source_manifest: list[dict[str, Any]] = []

    def get_source(pmcid: str) -> tuple[bytes, ET.Element]:
        if pmcid not in cache:
            cache[pmcid] = fetch_xml(pmcid)
            time.sleep(0.35)
        return cache[pmcid]

    for idx, (citing_pmcid, cited_pmcid, rid) in enumerate(SELECTED, 1):
        source = source_by_key[(citing_pmcid, cited_pmcid, rid)]
        citing_bytes, citing_root = get_source(citing_pmcid)
        cited_bytes, cited_root = get_source(cited_pmcid)
        citing_license = license_url(citing_root)
        cited_license = license_url(cited_root)
        if not citing_license or not cited_license:
            raise RuntimeError(f"missing explicit license: {citing_pmcid}={citing_license!r}, {cited_pmcid}={cited_license!r}")
        context_marked = find_marked_paragraph(citing_root, rid, cited_pmcid)
        if f"<CITED:{cited_pmcid}|" not in context_marked:
            raise RuntimeError(f"citation marker not found after serialization: {citing_pmcid}/{rid}")
        citing_file = RAW / f"{citing_pmcid}.xml"
        cited_file = RAW / f"{cited_pmcid}.xml"
        if not citing_file.exists():
            citing_file.write_bytes(citing_bytes)
        if not cited_file.exists():
            cited_file.write_bytes(cited_bytes)
        candidate_id = f"PMC-OA-V3-{idx:02d}"
        cited_abs = abstract_text(cited_root)
        record = {
            "candidate_id": candidate_id,
            "natural_or_constructed": "natural",
            "candidate_status": "待双方盲标",
            "screening_stage": "开放全文已取得；候选池待独立标注",
            "citing_pmcid": citing_pmcid,
            "citing_title": article_title(citing_root),
            "citing_doi": article_doi(citing_root),
            "citing_license": citing_license,
            "citing_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{citing_pmcid}/",
            "citing_xml_sha256": sha256(citing_bytes),
            "citing_context": source["citation_paragraph"],
            "citing_context_marked": context_marked,
            "citing_sentence_marked": None,
            "citing_sentence_status": "未自动断句；以含精确引用标记的完整段落为准",
            "citing_xml_locator": f"PMC fullTextXML; bibliography_xref={rid}; paragraph containing xref",
            "cited_pmcid": cited_pmcid,
            "cited_title": article_title(cited_root),
            "cited_doi": article_doi(cited_root),
            "cited_license": cited_license,
            "cited_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{cited_pmcid}/",
            "cited_xml_sha256": sha256(cited_bytes),
            "cited_evidence": cited_abs,
            "evidence_locator": f"PMC fullTextXML; {cited_pmcid}; section=ABSTRACT; exact normalized abstract text",
            "evidence_status": "已取得被引全文与摘要；是否支持施引主张待盲标",
            "overlap_status": "未在现有 v1/v2 candidate pool 中检出；完整 train/dev/test/调参/评测清单仍需最终交叉核对",
            "overlap_checked_against": "repo v1/v2 candidate pools; full split manifests pending",
            "annotator_1_label": None,
            "annotator_1_evidence_status": None,
            "annotator_1_evidence_locator": None,
            "annotator_1_reason": None,
            "annotator_2_label": None,
            "annotator_2_evidence_status": None,
            "annotator_2_evidence_locator": None,
            "annotator_2_reason": None,
            "adjudicated_label": None,
            "adjudication_status": "待双方独立标注与共同裁决",
            "source_retrieved_at": retrieved_at,
        }
        if not cited_abs:
            raise RuntimeError(f"cited abstract missing: {cited_pmcid}")
        records.append(record)
        source_manifest.extend([
            {
                "candidate_id": candidate_id,
                "role": "citing",
                "pmcid": citing_pmcid,
                "url": record["citing_url"],
                "license": citing_license,
                "xml_sha256": record["citing_xml_sha256"],
                "local_snapshot": str(citing_file.relative_to(REPO)).replace("\\", "/"),
            },
            {
                "candidate_id": candidate_id,
                "role": "cited",
                "pmcid": cited_pmcid,
                "url": record["cited_url"],
                "license": cited_license,
                "xml_sha256": record["cited_xml_sha256"],
                "local_snapshot": str(cited_file.relative_to(REPO)).replace("\\", "/"),
            },
        ])

    out_json = OUT_DATA / "pmc_oa_candidate_pool_ly_v3_2026-10-05.json"
    out_json.write_text(json.dumps({
        "schema_version": "candidate-pool-v3",
        "retrieved_at": retrieved_at,
        "source_policy": "PMC open-access fullTextXML; complete citing paragraph with exact bibliography marker; cited abstract retained for blind review",
        "selection": {
            "target_new_records": 10,
            "citing_articles": sorted({r["citing_pmcid"] for r in records}),
            "excluded_existing_candidate_pool": "v1/v2 PMCID set",
            "not_final_trial_set": True,
        },
        "records": records,
        "source_manifest": source_manifest,
        "qa": {
            "record_count": len(records),
            "unique_citing_pmcids": len({r["citing_pmcid"] for r in records}),
            "unique_cited_pmcids": len({r["cited_pmcid"] for r in records}),
            "all_citing_xml_hashes_present": all(r["citing_xml_sha256"] for r in records),
            "all_cited_xml_hashes_present": all(r["cited_xml_sha256"] for r in records),
            "all_licenses_explicit": all(r["citing_license"] and r["cited_license"] for r in records),
            "all_markers_present": all("<CITED:" in r["citing_context_marked"] for r in records),
            "labels_left_blank": all(r["adjudicated_label"] is None for r in records),
        },
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    common_fields = [
        "candidate_id", "natural_or_constructed", "candidate_status", "citing_pmcid", "citing_title", "citing_doi",
        "citing_url", "citing_license", "citing_xml_sha256", "citing_context_marked", "citing_xml_locator",
        "cited_pmcid", "cited_title", "cited_doi", "cited_url", "cited_license", "cited_xml_sha256",
        "cited_evidence", "evidence_locator", "evidence_status", "overlap_status", "source_retrieved_at",
    ]
    # Clean blind sheet: no labels, reasons, or adjudication values.
    blind_path = OUT_RESULT / "pmc_oa_v3_10_candidates_chen_blind_annotation_v1.csv"
    blind_fields = common_fields + [
        "annotator_1_label", "annotator_1_evidence_status", "annotator_1_evidence_locator", "annotator_1_reason",
    ]
    with blind_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=blind_fields)
        writer.writeheader()
        for r in records:
            out = {k: r.get(k) for k in blind_fields}
            writer.writerow(out)

    # Li Yun's independent review sheet starts blank by design; it is the side
    # that can be filled locally without seeing Chen's labels.
    ly_path = OUT_RESULT / "pmc_oa_v3_10_candidates_ly_independent_annotation_v1.csv"
    ly_fields = common_fields + [
        "annotator_2_label", "annotator_2_evidence_status", "annotator_2_evidence_locator", "annotator_2_reason",
    ]
    with ly_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ly_fields)
        writer.writeheader()
        for r in records:
            out = {k: r.get(k) for k in ly_fields}
            writer.writerow(out)

    manifest_path = OUT_RESULT / "pmc_oa_v3_source_manifest_2026-10-05.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(source_manifest[0]))
        writer.writeheader()
        writer.writerows(source_manifest)

    report = OUT_RESULT / "pmc_oa_v3_candidate_pool_report_2026-10-05.md"
    report.write_text(f"""# PMC natural 候选池 v3（10 条）

状态：候选池已准备，尚未形成最终试标集。10 条均保留完整施引段落、精确引用标记、被引全文摘要、来源 URL、许可和 XML SHA-256；两位标注者字段均留空。

## 数量与来源

- 新候选：{len(records)} 条
- 施引论文：{len({r['citing_pmcid'] for r in records})} 篇（{', '.join(sorted({r['citing_pmcid'] for r in records}))}）
- 被引论文：{len({r['cited_pmcid'] for r in records})} 篇
- 来源：Europe PMC fullTextXML / PMC OA 页面
- 许可：每条的施引和被引 XML 均取得显式许可 URL，具体见 `pmc_oa_v3_source_manifest_2026-10-05.csv`

## 核查边界

候选已与仓库中的 v1/v2 PMC 候选池去重；当前仓库未发现这些 PMCID 已进入现有候选池。正式纳入前仍需用完整的 Train/Dev/Test、调参和评测清单再做一次交叉核对，因此 `overlap_status` 没有写成“已确认无重叠”。

## 下一步

1. 李云填写 `pmc_oa_v3_10_candidates_ly_independent_annotation_v1.csv`。
2. 将不含李云标签的 `pmc_oa_v3_10_candidates_chen_blind_annotation_v1.csv` 发给陈明进独立标注。
3. 收回后保留双方原始表，逐条对照并共同裁决；在此之前不写 `adjudicated_label`，不计入最终合格条数。

## 质量闸门

- 记录数：{len(records)}
- 施引 XML 哈希齐全：是
- 被引 XML 哈希齐全：是
- 显式许可齐全：是
- 精确引用标记齐全：是
- 最终标签：全部留空（待双方盲标）
""", encoding="utf-8")

    print(json.dumps({
        "records": len(records),
        "unique_citing": len({r["citing_pmcid"] for r in records}),
        "unique_cited": len({r["cited_pmcid"] for r in records}),
        "out_json": str(out_json),
        "blind_csv": str(blind_path),
        "ly_csv": str(ly_path),
        "manifest_csv": str(manifest_path),
        "report": str(report),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
