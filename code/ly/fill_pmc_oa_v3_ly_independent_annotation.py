"""Fill Li Yun's independent side for the 10-record PMC candidate pool.

The Chen blind sheet is never modified by this script. Each evidence passage is
copied from the saved cited-article XML and paired with a paragraph-index
locator. Labels are deliberately conservative where the cited passage only
partially supports the citing claim.
"""

from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REPO = ROOT / ".repo_upload"
POOL = REPO / "data" / "interim" / "pmc_oa_candidate_pool_ly_v3_2026-10-05.json"
RAW = REPO / "data" / "raw" / "pmc_oa_v3_source_xml"
OUT = REPO / "results" / "ly" / "task3_natural_trial" / "pmc_oa_v3_10_candidates_ly_independent_annotation_v1.csv"
REPORT = REPO / "results" / "ly" / "task3_natural_trial" / "pmc_oa_v3_ly_independent_review_notes_2026-10-05.md"


# Root-level p indices are counted against the saved fullTextXML snapshot. The
# passages were checked against the source before writing this table.
REVIEW = {
    "PMC-OA-V3-01": {
        "label": "ACCURATE",
        "p": 4,
        "status": "已定位",
        "reason": "被引原文在该段明确说明牙科生物陶瓷具有低细胞毒性，并处于生物相容性/内镜治疗语境；支持施引段关于理想根管封闭材料应具生物相容性且低毒性的主张。",
    },
    "PMC-OA-V3-02": {
        "label": "ACCURATE",
        "p": 6,
        "status": "已定位",
        "reason": "被引原文明确把根管封闭剂的溶解度、碱性、生物活性和膜厚度与封闭及操作性能联系起来，支持施引段关于封闭剂应具备适当理化性质的概括。",
    },
    "PMC-OA-V3-03": {
        "label": "ACCURATE",
        "p": 12,
        "status": "已定位",
        "reason": "被引综述直接定义根管封闭剂对根管牙本质的黏附，并将黏附列为理想根管封闭剂性质之一，支持施引段的黏附定义；施引段关于 push-out 的实验解释属于施引方自己的方法说明。",
    },
    "PMC-OA-V3-04": {
        "label": "ACCURATE",
        "p": 2,
        "status": "已定位",
        "reason": "被引原文逐项报告 AH-Plus 在干燥根管中粘结强度最高、CHX 会降低 BC sealer 粘结强度，且与施引段所述比较方向一致。",
    },
    "PMC-OA-V3-05": {
        "label": "NOT_ACCURATE",
        "p": 43,
        "status": "已定位",
        "reason": "被引原文支持 Ser8 与 α-羟基酸的立体/手性选择性和对映选择性，但在可定位段落中没有支持施引段所说的“手性偏好降低、反同手性偏好”这一更具体结论，因此不能判为完整支持。",
    },
    "PMC-OA-V3-06": {
        "label": "NOT_ACCURATE",
        "p": 4,
        "status": "已定位",
        "reason": "被引原文确实讨论前生物化学和陨石中的羟基酸，但定位段没有出现施引段所指的 isoVal 或该化合物在陨石样本中的具体结论；属于主题相关但证据不足以支持该具体表述。",
    },
    "PMC-OA-V3-07": {
        "label": "NOT_ACCURATE",
        "p": 7,
        "status": "已定位",
        "reason": "被引原文说明质谱蛋白质组学具有较高灵敏度和通量，并用于发现手性相关蛋白修饰，但没有直接支持施引段“质谱提供简单快速的手性探索”这一方法学概括；保守标为不准确。",
    },
    "PMC-OA-V3-08": {
        "label": "ACCURATE",
        "p": 0,
        "status": "已定位",
        "reason": "被引综述直接说明 PNN 包围神经元并参与可塑性和记忆调节，且讨论 PNN 降解/重塑对记忆的影响，支持施引段的核心主张。",
    },
    "PMC-OA-V3-09": {
        "label": "ACCURATE",
        "p": 1,
        "status": "已定位",
        "reason": "被引综述明确说明 HA 是神经组织 ECM 的信号分子，可调节星形胶质细胞、小胶质细胞等细胞过程，并影响神经炎症，支持施引段关于 HA-rich ECM 与胶质激活/炎症信号关系的概括。",
    },
    "PMC-OA-V3-10": {
        "label": "ACCURATE",
        "p": 3,
        "status": "已定位",
        "reason": "被引综述明确说明脑衰老伴随胶质炎症、胶质反应性改变、神经元支持丧失和神经退行性损伤，支持施引段关于脑衰老胶质改变及其后果的主张。",
    },
}


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def source_paragraph(pmcid: str, index: int) -> str:
    root = ET.parse(RAW / f"{pmcid}.xml").getroot()
    for e in root.iter():
        e.tag = e.tag.rsplit("}", 1)[-1]
    paragraphs = list(root.iter("p"))
    if index >= len(paragraphs):
        raise RuntimeError(f"paragraph index out of range: {pmcid} p={index}")
    text = clean("".join(paragraphs[index].itertext()))
    if len(text) < 40:
        raise RuntimeError(f"evidence paragraph unexpectedly short: {pmcid} p={index}")
    return text


def main() -> None:
    obj = json.loads(POOL.read_text(encoding="utf-8"))
    records = obj["records"]
    if set(REVIEW) != {r["candidate_id"] for r in records}:
        raise RuntimeError("review mapping does not cover exactly the 10 candidate IDs")

    fields = [
        "candidate_id", "natural_or_constructed", "candidate_status", "citing_pmcid", "citing_title", "citing_doi",
        "citing_url", "citing_license", "citing_xml_sha256", "citing_context_marked", "citing_xml_locator",
        "cited_pmcid", "cited_title", "cited_doi", "cited_url", "cited_license", "cited_xml_sha256",
        "cited_evidence", "evidence_locator", "evidence_status", "overlap_status", "source_retrieved_at",
        "annotator_2_label", "annotator_2_evidence_status", "annotator_2_evidence_locator",
        "annotator_2_evidence_text", "annotator_2_reason", "annotator_2_review_status",
    ]
    rows = []
    for r in records:
        item = REVIEW[r["candidate_id"]]
        text = source_paragraph(r["cited_pmcid"], item["p"])
        locator = f"PMC fullTextXML; {r['cited_pmcid']}; root p index={item['p']}; saved snapshot {r['cited_xml_sha256']}"
        out = {k: r.get(k) for k in fields}
        out.update({
            "annotator_2_label": item["label"],
            "annotator_2_evidence_status": item["status"],
            "annotator_2_evidence_locator": locator,
            "annotator_2_evidence_text": text,
            "annotator_2_reason": item["reason"],
            "annotator_2_review_status": "李云独立初标完成；待陈明进盲标，不是最终裁决",
        })
        rows.append(out)

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    counts = {}
    for r in rows:
        counts[r["annotator_2_label"]] = counts.get(r["annotator_2_label"], 0) + 1
    REPORT.write_text("""# PMC natural 候选 v3：李云独立初标说明

本文件只记录李云侧的独立初标，陈明进盲标表单独保存且不含这些字段。10 条仍属于候选试标，不计入最终合格样本，直到双方各自标注、对照并共同裁决。

## 本次初标数量

- ACCURATE：{accurate}
- NOT_ACCURATE：{not_accurate}
- IRRELEVANT：{irrelevant}
- 总计：{total}

`evidence_text` 均从保存的被引 PMC fullTextXML 逐段读取，`evidence_locator` 给出 PMCID、根级 p 索引和 XML SHA-256。NOT_ACCURATE 的记录保留了真实可定位段落，但理由明确说明具体主张没有被该段完整支持。结果不是最终裁决，也没有改写陈明进侧文件。
""".format(
        accurate=counts.get("ACCURATE", 0),
        not_accurate=counts.get("NOT_ACCURATE", 0),
        irrelevant=counts.get("IRRELEVANT", 0),
        total=len(rows),
    ), encoding="utf-8")
    print({"rows": len(rows), "counts": counts, "output": str(OUT)})


if __name__ == "__main__":
    main()
