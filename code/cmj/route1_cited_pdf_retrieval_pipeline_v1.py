# -*- coding: utf-8 -*-
"""路线一 被引全文证据检索端到端流程（原型 v1）。

目标：把"被引 PDF/XML 全文 -> BM25 候选证据 -> v2 模型输入"接通到真实论文上。

与冻结 v2 的关系：
  - 冻结 Sarol v2 的候选证据只来自被引文献的摘要句（原始 corpus 只有 abstract）；
    本流程在被引文献 PMC JATS 全文（abstract + body 各 sec）上检索，是"被引 PDF 证据检索"
    的原型实现，不改动任何已冻结数据。
  - 分词、BM25 参数（k1=1.2, b=0.75）、平局规则、system_prompt、user_prompt 渲染、
    input_sha256 口径全部复用 code/ly/build_sarol_inputs_v2.py，保证模型可见格式与冻结实验一致。

输入：
  - 真实 PMC OA 引用边候选池 JSON（含 citing_context_marked 与 cited_pmcid）
  - 被引 PMC JATS 全文 XML 目录

输出（每条引用边一条记录）：
  - *.inputs.jsonl       与 v2 同构的模型输入（system_prompt/user_prompt/candidate_evidence/
                         allowed_evidence_ids/input_sha256）
  - *.locators.jsonl     每条候选证据在被引全文中的精确定位（section/段落/段内句序/字符偏移）
  - *.manifest.json      源文件哈希、检索配置、统计与"无 gold（待盲标）"声明

真实边在候选池中尚未裁决，故不写 gold；模型在 A100 上对 inputs 做推理给出预测，
人工盲标裁决在后。原型只演示流程，不参与正式指标。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ---- 复用冻结 v2 的分词 / BM25 / prompt 渲染 / 哈希口径（不复制实现，避免漂移）----
REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILDER_PATH = REPO_ROOT / "code" / "ly" / "build_sarol_inputs_v2.py"
_spec = importlib.util.spec_from_file_location("build_sarol_inputs_v2", _BUILDER_PATH)
v2 = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("build_sarol_inputs_v2", v2)
_spec.loader.exec_module(v2)

SYSTEM_PROMPT = v2.SYSTEM_PROMPT
TOP_K = 10
SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
CITED_MARK_RE = re.compile(r"\s*<CITED:[^>]+>\s*")
OTHER_MARK_RE = re.compile(r"\s*<OTHER_CITATION:[^>]+>\s*")
# 常见缩写，切句时临时保护其中的句点，避免 "et al." 等误断
_ABBREVIATIONS = ["et al.", "e.g.", "i.e.", "vs.", "figs.", "fig.", "etc.",
                  "dr.", "prof.", "no.", "pp.", "vol.", "st.", "mr.", "ms.",
                  "approx.", "inc.", "ltd.", "al."]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def split_sentences(paragraph_text: str) -> list[str]:
    """缩写感知的句切分，避免 et al. 等把正文切成残句，返回去空白后的非空句。"""
    protected = paragraph_text
    for i, ab in enumerate(_ABBREVIATIONS):
        protected = re.sub(re.escape(ab), ab.replace(".", f"\x00{i}\x00"),
                           protected, flags=re.IGNORECASE)
    out = []
    for sent in SENT_SPLIT_RE.split(protected):
        for i in range(len(_ABBREVIATIONS)):
            sent = sent.replace(f"\x00{i}\x00", ".")
        sent = re.sub(r"\s+", " ", sent).strip()
        # 过滤过短残句与明显的作者名残片（以 et al. 结尾）
        if len(sent) >= 10 and not re.search(r"\bet al\.?$", sent):
            out.append(sent)
    return out


def _element_text(elem: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip()


def parse_jats_fulltext(xml_path: Path, pmcid: str) -> list[dict]:
    """解析 PMC JATS XML，返回全文句段，每句带 section/段落/句子/字符偏移。

    abstract 下的 p 标记为 section=ABSTRACT；body 下递归遍历 sec，
    每个 sec 只取其直接子 p（避免嵌套 sec 重复），section 取最近标题路径。
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    sentences: list[dict] = []
    para_idx = 0

    def add_paragraph(section: str, p_elem: ET.Element):
        nonlocal para_idx
        text = _element_text(p_elem)
        if not text:
            return
        cursor = 0
        for s_idx, sent in enumerate(split_sentences(text)):
            # 段内字符偏移（在归一化段文本中定位）
            pos = text.find(sent, cursor)
            if pos < 0:
                pos = cursor
            char_offset = pos
            cursor = pos + len(sent)
            sentences.append({
                "source_pmcid": pmcid,
                "section": section,
                "paragraph_idx": para_idx,
                "sentence_idx": s_idx,
                "char_offset": char_offset,
                "text": sent,
            })
        para_idx += 1

    # 摘要：article/front/.../abstract（摘要通常直接含若干 p，含少量 sec/title 容器）
    for abstract in root.iter():
        if strip_ns(abstract.tag) != "abstract":
            continue
        for p in abstract.iter():
            if strip_ns(p.tag) == "p":
                add_paragraph("ABSTRACT", p)

    # 正文：递归遍历 body/sec
    body = None
    for elem in root.iter():
        if strip_ns(elem.tag) == "body":
            body = elem
            break

    def walk_sec(sec: ET.Element, title_path: str):
        title = title_path
        for child in sec:
            tag = strip_ns(child.tag)
            if tag == "title":
                title = _element_text(child) or title_path
            elif tag == "p":
                add_paragraph(title, child)
            elif tag == "sec":
                walk_sec(child, title)

    if body is not None:
        for child in body:
            tag = strip_ns(child.tag)
            if tag == "p":
                add_paragraph("BODY", child)
            elif tag == "sec":
                walk_sec(child, "BODY")

    # 去重：摘要句可能与正文重复（保留 section 归属，按全文唯一文本只保留首次）
    seen, unique = set(), []
    for s in sentences:
        key = s["text"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique


def extract_claim(citing_context_marked: str, cited_pmcid: str) -> str:
    """从含引用标记的施引语境中提取引用该被引文献的句子作为论断，清理标记。"""
    context = citing_context_marked or ""
    raw_sents = split_sentences(context)
    target = None
    for sent in raw_sents:
        if f"CITED:{cited_pmcid}" in sent:
            target = sent
            break
    if target is None:
        for sent in raw_sents:
            if "<CITED:" in sent:
                target = sent
                break
    if target is None:
        target = context
    claim = CITED_MARK_RE.sub(" ", target)
    claim = OTHER_MARK_RE.sub(" ", claim)
    claim = re.sub(r"\s+", " ", claim).strip()
    return claim


def build_record(edge: dict, xml_dir: Path) -> dict:
    cited = edge["cited_pmcid"]
    xml_path = xml_dir / f"{cited}.xml"
    if not xml_path.exists():
        raise FileNotFoundError(f"被引全文 XML 缺失: {xml_path}")

    claim = extract_claim(edge.get("citing_context_marked", ""), cited)

    # 全文句 -> 候选（单篇被引，文档序号 D01）
    fulltext = parse_jats_fulltext(xml_path, cited)
    candidates = []
    for s in fulltext:
        candidates.append({
            "doc_id": 1,            # 单篇被引，D01
            "sentence_id": s["sentence_idx"],
            "source_doc_rank": 1,
            "text": s["text"],
            "_loc": s,
        })

    # 与 v2 完全一致的 BM25 检索（原始候选句顺序 = 全文段落顺序）
    ranked = v2.bm25_rank(claim, candidates)[:TOP_K]
    # 单篇文档，compact 后 D01:S01..S10 按 BM25 排序顺序
    compacted = []
    for rank_i, item in enumerate(ranked, start=1):
        ci = dict(item)
        ci["evidence_id"] = f"D01:S{rank_i:02d}"
        loc = ci.pop("_loc")
        ci["source_doc_id"] = cited
        ci["section"] = loc["section"]
        ci["paragraph_idx"] = loc["paragraph_idx"]
        ci["paragraph_sentence_idx"] = loc["sentence_idx"]
        ci["char_offset"] = loc["char_offset"]
        compacted.append(ci)

    allowed = [item["evidence_id"] for item in compacted]
    # 模型可见的 candidate_evidence 与 v2 字段对齐（doc_id/sentence_id/source_doc_rank/text）
    visible_candidates = [{
        "evidence_id": item["evidence_id"],
        "doc_id": item["doc_id"],
        "sentence_id": item["sentence_id"],
        "source_doc_rank": item["source_doc_rank"],
        "text": item["text"],
    } for item in compacted]
    user_prompt = v2.render_user_prompt(claim, visible_candidates)

    # 校验模型可见证据编号格式
    assert all(re.fullmatch(r"D\d{2}:S\d{2}", x) for x in allowed)
    assert len(allowed) == len(set(allowed))

    input_row = {
        "claim_id": edge["candidate_id"],
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "candidate_evidence": visible_candidates,
        "allowed_evidence_ids": allowed,
        "input_sha256": v2.model_input_sha256(SYSTEM_PROMPT, user_prompt),
    }
    locator_row = {
        "candidate_id": edge["candidate_id"],
        "claim": claim,
        "citing_pmcid": edge["citing_pmcid"],
        "cited_pmcid": cited,
        "cited_xml": xml_path.name,
        "cited_xml_sha256": file_sha256(xml_path),
        "retriever": "BM25 fulltext (abstract+body), k1=1.2 b=0.75, same tokenizer/tie-break as frozen v2",
        "fulltext_sentence_count": len(fulltext),
        "evidence_locators": [{
            "evidence_id": item["evidence_id"],
            "cited_pmcid": cited,
            "section": item["section"],
            "paragraph_idx": item["paragraph_idx"],
            "paragraph_sentence_idx": item["paragraph_sentence_idx"],
            "char_offset": item["char_offset"],
            "text": item["text"],
        } for item in compacted],
    }
    return {"input": input_row, "locator": locator_row,
            "claim": claim, "n_full": len(fulltext)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pool", type=Path,
                    default=REPO_ROOT / "data/interim/pmc_oa_candidate_pool_ly_v3_2026-10-05.json")
    ap.add_argument("--xml-dir", type=Path,
                    default=REPO_ROOT / "data/raw/pmc_oa_v3_source_xml")
    ap.add_argument("--edges", nargs="+", default=["PMC-OA-V3-01", "PMC-OA-V3-08"],
                    help="要演示的真实引用边 candidate_id")
    ap.add_argument("--output-dir", type=Path,
                    default=REPO_ROOT / "results/cmj/cited_pdf_retrieval_v1_2026-10-18")
    args = ap.parse_args()

    pool = json.loads(args.pool.read_text(encoding="utf-8"))
    edges_by_id = {r["candidate_id"]: r for r in pool["records"]}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    inputs, locators = [], []
    edge_summaries = []
    for edge_id in args.edges:
        edge = edges_by_id[edge_id]
        rec = build_record(edge, args.xml_dir)
        inputs.append(rec["input"])
        locators.append(rec["locator"])
        edge_summaries.append({
            "candidate_id": edge_id,
            "citing_pmcid": edge["citing_pmcid"],
            "cited_pmcid": edge["cited_pmcid"],
            "cited_title": edge.get("cited_title"),
            "fulltext_sentences": rec["n_full"],
            "top1_evidence_id": rec["input"]["allowed_evidence_ids"][0],
            "top1_section": rec["locator"]["evidence_locators"][0]["section"],
        })
        print(f"[OK] {edge_id}: {edge['citing_pmcid']} -> {edge['cited_pmcid']} "
              f"| fulltext {rec['n_full']} 句 | claim: {rec['claim'][:70]}...", flush=True)

    inputs_path = args.output_dir / "cited_pdf_demo.inputs.jsonl"
    locators_path = args.output_dir / "cited_pdf_demo.locators.jsonl"
    with inputs_path.open("wb") as fh:
        for row in inputs:
            fh.write((json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))
    with locators_path.open("wb") as fh:
        for row in locators:
            fh.write((json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))

    manifest = {
        "manifest_version": "cited_pdf_retrieval_v1_2026-10-18",
        "purpose": "被引全文(PMC JATS XML)证据检索端到端原型；接通真实两篇被引文献到 v2 模型输入",
        "builder": "code/cmj/route1_cited_pdf_retrieval_pipeline_v1.py",
        "builder_sha256": file_sha256(Path(__file__)),
        "edge_pool": str(args.pool.relative_to(REPO_ROOT)),
        "edges": args.edges,
        "retrieval": {
            "corpus": "被引文献 PMC JATS 全文：abstract + body 所有 sec 段落",
            "top_k": TOP_K,
            "bm25_k1": 1.2, "bm25_b": 0.75,
            "consistency": "分词/BM25/平局规则/prompt渲染/sha256 全部复用 code/ly/build_sarol_inputs_v2.py",
            "difference_from_frozen_v2": "冻结 Sarol v2 仅检索摘要句；本流程检索全文句并保留 section/段落/字符偏移",
        },
        "gold_policy": "真实边候选池未裁决(adjudicated_label=null)，不写 gold、不参与指标；模型 A100 推理后人工盲标裁决",
        "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "edges_summary": edge_summaries,
        "outputs": {
            "inputs": {"path": str(inputs_path.relative_to(REPO_ROOT)), "sha256": file_sha256(inputs_path), "records": len(inputs)},
            "locators": {"path": str(locators_path.relative_to(REPO_ROOT)), "sha256": file_sha256(locators_path), "records": len(locators)},
        },
        "model_inference": "需在 A100 用冻结 adapter 对 cited_pdf_demo.inputs.jsonl 推理；本地仅产出输入",
    }
    manifest_path = args.output_dir / "cited_pdf_demo.manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"\n[DONE] 输入: {inputs_path}")
    print(f"[DONE] 定位: {locators_path}")
    print(f"[DONE] 清单: {manifest_path}")


if __name__ == "__main__":
    main()
