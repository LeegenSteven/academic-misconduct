#!/usr/bin/env python3
"""Recover Sarol labels from the pinned original annotations without guessed labels.

Standard library only. Run --help for the local-source and download commands.
Original files and published split membership are never modified.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

SOURCE_URL = "https://github.com/ScienceNLP-Lab/Citation-Integrity.git"
SOURCE_COMMIT = "e9823957bb263db9ae402351b76d88ff1a723712"
SCHEMA_VERSION = "sarol-quality-v1"
LABEL_MAP = {
    "ACCURATE": "ACCURATE", "INDIRECT": "ACCURATE",
    "INDIRECT_NOT_REVIEW": "ACCURATE", "CONTRADICT": "NOT_ACCURATE",
    "NOT_SUBSTANTIATE": "NOT_ACCURATE", "OVERSIMPLIFY": "NOT_ACCURATE",
    "MISQUOTE": "NOT_ACCURATE", "ETIQUETTE": "NOT_ACCURATE",
    "IRRELEVANT": "IRRELEVANT",
}
EXPECTED_COUNTS = {"Train": 2141, "Dev": 316, "Test": 606}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def dump_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dump_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})


def counts(values) -> dict:
    return dict(collections.Counter("UNRESOLVED" if value is None else value for value in values))


def normalize(text: str, relaxed: bool = False) -> str:
    # Marker wrappers are format changes; other punctuation remains in strict matching.
    text = re.sub(r"\[?<\|(?:multi_)?cit\|>\]?", " M ", text, flags=re.I)
    text = re.sub(r"\[?<\|other_cit\|>\]?", " O ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return "".join(c for c in text if c.isalnum()) if relaxed else text


def annotation_variants(annotation: dict) -> list[str]:
    contexts = sorted(annotation.get("citation_context", []), key=lambda item: item["start"])
    if not contexts:
        return []
    # Annotations can be out of order and have small gaps. The claim can retain the gap.
    joined = " ".join(c["text"] for c in contexts)
    bounding = annotation["citing_paragraph"][min(c["start"] for c in contexts):max(c["end"] for c in contexts)]
    return [joined, bounding]


def legacy_first_context_match(claim: str, annotations: list[dict]) -> dict | None:
    """Reproduce the old converter's bug for comparison, never for new labels."""
    def old_normalize(text):
        return re.sub(r"\s+", " ", text.replace("[<|cit|>]", "M").replace("[<|multi_cit|>]", "M")).strip().lower()
    key = old_normalize(claim)
    for annotation in annotations:
        first = (annotation.get("citation_context") or [{}])[0].get("text", "")
        context = old_normalize(first)
        if context and (context == key or context in key):
            return annotation
    return None


def source_segment_location(text: str, segment: dict) -> dict:
    """Correct only unique exact/whitespace text locations; preserve old offsets."""
    start, end, evidence = segment["start"], segment["end"], segment["text"]
    if text[start:end] == evidence:
        return {"location_status": "offset_exact", "corrected_start": start, "corrected_end": end}
    positions = [m.start() for m in re.finditer(re.escape(evidence), text)] if evidence else []
    if len(positions) == 1:
        return {"location_status": "offset_recovered_unique_text", "corrected_start": positions[0],
                "corrected_end": positions[0] + len(evidence)}
    # Whitespace-only normalization is safe for the figure-caption newline discrepancy.
    offsets = [i for i, c in enumerate(text) if not c.isspace()]
    compact = "".join(text[i] for i in offsets)
    needle = "".join(c for c in evidence if not c.isspace())
    matches = [m.start() for m in re.finditer(re.escape(needle), compact)] if needle else []
    if len(matches) == 1:
        match = matches[0]
        return {"location_status": "offset_recovered_unique_whitespace", "corrected_start": offsets[match],
                "corrected_end": offsets[match + len(needle) - 1] + 1}
    return {"location_status": "ambiguous_text_location" if positions or matches else "text_not_found",
            "corrected_start": None, "corrected_end": None}


def mapped_evidence_gold(evidence: dict) -> str | None:
    labels = {LABEL_MAP.get(ev["label"]) for entries in evidence.values() for ev in entries}
    if not labels or None in labels:
        return None
    if labels == {"IRRELEVANT"}:
        return "IRRELEVANT"
    if "NOT_ACCURATE" in labels:
        return "NOT_ACCURATE"
    if labels == {"ACCURATE"}:
        return "ACCURATE"
    # Mixed accurate/irrelevant evidence is a review case, not an implicit default.
    return None


def retrieve_source(destination: Path, expected_commit: str) -> Path:
    created = not destination.exists()
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-c", "http.sslBackend=openssl", "-c", "core.autocrlf=false", "clone",
                        "--no-checkout", SOURCE_URL, str(destination)], check=True)
    git_prefix = ["git", "-c", f"safe.directory={destination.resolve().as_posix()}", "-C", str(destination)]
    current = subprocess.check_output(git_prefix + ["status", "--porcelain"], text=True) if not created else ""
    if current.strip():
        raise ValueError("Source checkout has local changes; choose another --download-dir.")
    subprocess.run(git_prefix + ["-c", "core.autocrlf=false", "checkout", "--detach", expected_commit], check=True)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, help="Official Citation-Integrity checkout (not its Data subdirectory)")
    parser.add_argument("--download", action="store_true", help="Download and check out the pinned official commit")
    parser.add_argument("--download-dir", type=Path, help="Reusable official source checkout; default <out>/_sources/Citation-Integrity")
    parser.add_argument("--expected-commit", default=SOURCE_COMMIT)
    parser.add_argument("--legacy-dir", type=Path, help="Existing converted-three-class-v2 folder; optional comparison only")
    parser.add_argument("--out", type=Path, default=Path("data/quality_v1/sarol"))
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.download:
        if args.source_dir:
            parser.error("Choose --source-dir or --download, not both.")
        source = retrieve_source(args.download_dir or out / "_sources" / "Citation-Integrity", args.expected_commit).resolve()
    elif args.source_dir:
        source = args.source_dir.resolve()
    else:
        parser.error("Specify --source-dir or --download.")
    # Trust only the explicit source checkout for this command; no global Git setting is changed.
    git_prefix = ["git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source)]
    actual_commit = subprocess.check_output(git_prefix + ["rev-parse", "HEAD"], text=True).strip()
    if actual_commit != args.expected_commit:
        raise ValueError(f"Source commit {actual_commit} differs from expected {args.expected_commit}.")
    source_changes = subprocess.check_output(git_prefix + ["status", "--porcelain", "--untracked-files=no"], text=True)
    if source_changes.strip():
        raise ValueError("Official source checkout contains modified tracked files; use a clean source checkout.")
    data = source / "Data"
    source_files = ["LICENSE", "README.md", "Data/annotations.zip", "Data/train.jsonl", "Data/dev.jsonl", "Data/test.jsonl"]
    source_files += ["Data/multivers-format/" + name for name in ["corpus.jsonl", "claims-train.jsonl", "claims-dev.jsonl", "claims-test.jsonl"]]
    source_manifest = []
    for name in source_files:
        raw = (source / name).read_bytes()
        source_manifest.append({"path": name, "source_url": f"https://github.com/ScienceNLP-Lab/Citation-Integrity/blob/{actual_commit}/{name}",
                                "bytes_on_disk": len(raw), "sha256_on_disk": sha(raw),
                                "sha256_lf": sha(raw.replace(b"\r\n", b"\n")),
                                "newline_note": "Git checkout may translate LF to CRLF; LF hash identifies the original logical text." if name.endswith((".jsonl", ".md")) else "Binary bytes unchanged."})
    dump_json(out / "source_manifest.json", {"source_repository": SOURCE_URL, "source_commit": actual_commit,
              "source_license": "MIT in repository LICENSE; the underlying article texts retain their original provenance.",
              "files": source_manifest})
    corpus_rows = load_jsonl(data / "multivers-format" / "corpus.jsonl")
    corpus = {str(row["doc_id"]): row for row in corpus_rows}
    if len(corpus) != len(corpus_rows):
        raise ValueError("Duplicate corpus doc_id.")
    corpus_map, reference_groups = {}, {}
    annotations = collections.defaultdict(lambda: collections.defaultdict(list))
    annotation_order = collections.defaultdict(list)
    segment_audit, reference_text_cache = [], {}
    with zipfile.ZipFile(data / "annotations.zip") as archive:
        for name in archive.namelist():
            if name.startswith("__MACOSX") or not name.endswith(".json"):
                continue
            parts = name.split("/")
            if len(parts) >= 5 and parts[2] == "citations":
                split, ref_id = parts[1], parts[3]
                record = json.loads(archive.read(name))
                record.update({"annotation_path": name, "cited_reference_group_id": ref_id,
                               "cited_pmcid": ref_id.split("_", 1)[1],
                               "citing_pmcid": Path(name).stem.split("_", 1)[0]})
                source_ref = f"annotations/{split}/references/{ref_id}.txt"
                if source_ref not in reference_text_cache:
                    raw_text = archive.read(source_ref)
                    reference_text_cache[source_ref] = (raw_text.decode("utf-8-sig"), sha(raw_text))
                text, reference_sha = reference_text_cache[source_ref]
                locations = []
                for segment_index, segment in enumerate(record.get("evidence_segments", [])):
                    location = {"annotation_path": name, "segment_index_0based": segment_index,
                                "source_reference_file": source_ref, "source_reference_sha256": reference_sha,
                                "original_start": segment["start"], "original_end": segment["end"],
                                "evidence_text": segment["text"], **source_segment_location(text, segment)}
                    locations.append(location)
                    segment_audit.append(location)
                record["evidence_segment_source_locations"] = locations
                annotations[split][ref_id].append(record)
                annotation_order[split].append(record)
            elif len(parts) == 4 and parts[2] == "references_sentence":
                split, ref_id = parts[1], Path(name).stem
                reference_groups[ref_id] = {"split": split, "cited_pmcid": ref_id.split("_", 1)[1]}
                for index, line in enumerate(archive.read(name).decode("utf-8-sig").splitlines()):
                    if not line.strip():
                        continue
                    block = json.loads(line)
                    doc_id = str(block["par_id"])
                    if doc_id in corpus_map:
                        raise ValueError(f"Corpus paragraph id occurs in multiple reference sources: {doc_id}")
                    if doc_id not in corpus or corpus[doc_id]["abstract"] != block["sentences"]:
                        raise ValueError(f"Reference paragraph does not match corpus: {doc_id}")
                    corpus_map[doc_id] = {"doc_id": doc_id, "cited_reference_group_id": ref_id,
                                          "cited_pmcid": ref_id.split("_", 1)[1], "split": split,
                                          "source_annotation_path": name, "source_jsonl_line_1based": index + 1,
                                          "sentence_count": len(block["sentences"]), "unit": "paragraph_block"}
    if set(corpus_map) != set(corpus):
        raise ValueError("Not every corpus record has an original reference paragraph mapping.")
    dump_jsonl(out / "corpus.jsonl", corpus_rows)
    dump_csv(out / "corpus_paragraph_to_paper.csv", list(corpus_map.values()), list(next(iter(corpus_map.values())).keys()))
    dump_csv(out / "original_evidence_segment_locations.csv", segment_audit,
             ["annotation_path", "segment_index_0based", "source_reference_file", "source_reference_sha256",
              "original_start", "original_end", "location_status", "corrected_start", "corrected_end", "evidence_text"])
    all_records, review_rows, legacy_differences, legacy_manifest = [], [], [], []
    split_stats = {}
    for split, expected in EXPECTED_COUNTS.items():
        claims = load_jsonl(data / "multivers-format" / f"claims-{split.lower()}.jsonl")
        if len(claims) != expected or len({str(c["id"]) for c in claims}) != expected:
            raise ValueError(f"Unexpected claim count or duplicate ids for {split}.")
        legacy = {}
        if args.legacy_dir:
            legacy_path = args.legacy_dir / f"claims-{split.lower()}.jsonl"
            if legacy_path.exists():
                legacy = {str(c["id"]): c for c in load_jsonl(legacy_path)}
                raw = legacy_path.read_bytes()
                legacy_manifest.append({"path": str(legacy_path.resolve()), "rows": len(legacy),
                                        "sha256_on_disk": sha(raw), "sha256_lf": sha(raw.replace(b"\r\n", b"\n"))})
        normalized, models = [], []
        for claim in claims:
            sample_id = f"sarol:{split.lower()}:{claim['id']}"
            refs = {corpus_map[str(doc_id)]["cited_reference_group_id"] for doc_id in claim["cited_doc_ids"]}
            if len(refs) != 1:
                raise ValueError(f"Claim {sample_id} does not identify one reference article group: {refs}")
            ref_id = next(iter(refs))
            candidates = annotations[split][ref_id]
            strict_key, loose_key = normalize(claim["claim"]), normalize(claim["claim"], True)
            matches = [a for a in candidates if strict_key in [normalize(v) for v in annotation_variants(a)]]
            method = "strict_sorted_context_or_bounding_span"
            if not matches:
                matches = [a for a in candidates if loose_key in [normalize(v, True) for v in annotation_variants(a)]]
                method = "alphanumeric_sorted_context_or_bounding_span"
            raw_labels = sorted({a["label"] for a in matches})
            mapped_labels = {LABEL_MAP.get(label) for label in raw_labels}
            raw_label = raw_labels[0] if len(raw_labels) == 1 else None
            gold = next(iter(mapped_labels)) if len(mapped_labels) == 1 and None not in mapped_labels else None
            if not matches:
                status = "unmatched"
                method = "none"
            elif len(matches) == 1:
                status = "unique"
            elif raw_label is not None:
                status = "label_resolved_source_ambiguous"
            else:
                status = "conflicting_annotation_labels"
            # All original alternatives survive; never pick the first ambiguous source.
            evidence_original = claim.get("evidence") or {}
            evidence_converted = {}
            evidence_texts, invalid_refs = [], []
            for doc_id, entries in evidence_original.items():
                for entry in entries:
                    converted_label = LABEL_MAP.get(entry.get("label"))
                    if converted_label is None:
                        invalid_refs.append(f"Unknown evidence label: {entry.get('label')}")
                    evidence_converted.setdefault(doc_id, []).append({**entry, "label": converted_label})
                    for sent_id in entry.get("sentences", []):
                        source_block = corpus.get(str(doc_id))
                        if source_block is None or not isinstance(sent_id, int) or not 0 <= sent_id < len(source_block["abstract"]):
                            invalid_refs.append(f"{doc_id}#{sent_id}")
                            continue
                        mapping = corpus_map[str(doc_id)]
                        evidence_texts.append({"doc_id": str(doc_id), "sentence_index_0based": sent_id,
                                               "text": source_block["abstract"][sent_id], "original_evidence_label": entry.get("label"),
                                               "source_reference_file": mapping["source_annotation_path"],
                                               "source_jsonl_line_1based": mapping["source_jsonl_line_1based"],
                                               "locator": f"{mapping['source_annotation_path']}@line={mapping['source_jsonl_line_1based']};sentence={sent_id}"})
            has_raw_segments = any(a.get("evidence_segments") for a in matches)
            missing_reason = None
            if not evidence_texts:
                missing_reason = "conversion_did_not_locate_annotated_segments" if has_raw_segments else "no_original_evidence_segments"
            citing_ids = sorted({a["citing_pmcid"] for a in matches})
            evidence_gold = mapped_evidence_gold(evidence_original)
            old_gold = (legacy.get(str(claim["id"])) or {}).get("gold")
            row = {"schema_version": SCHEMA_VERSION, "dataset": "Sarol2024_CitationIntegrity", "sample_id": sample_id,
                   "id": str(claim["id"]), "split": split.lower(), "claim": claim["claim"],
                   "gold": gold, "project_label": gold, "raw_label": raw_label, "raw_label_candidates": raw_labels,
                   "is_indirect": raw_label in {"INDIRECT", "INDIRECT_NOT_REVIEW"},
                   "annotation_alignment_status": status, "annotation_match_method": method,
                   "annotation_paths": sorted(a["annotation_path"] for a in matches),
                   "citing_pmcid": citing_ids[0] if len(citing_ids) == 1 else None,
                   "citing_pmcid_candidates": citing_ids, "cited_reference_group_id": ref_id,
                   "cited_pmcid": reference_groups[ref_id]["cited_pmcid"],
                   "cited_doc_ids": claim["cited_doc_ids"], "evidence": evidence_original,
                   "evidence_three_class": evidence_converted, "evidence_texts": evidence_texts,
                   "evidence_status": "源文缺失" if invalid_refs else "已定位" if evidence_texts else "待定位",
                   "evidence_missing": not bool(evidence_texts), "evidence_missing_reason": missing_reason,
                   "raw_annotation_has_evidence_segments": has_raw_segments,
                   "evidence_reference_errors": invalid_refs, "evidence_derived_project_label": evidence_gold,
                   "evidence_label_disagrees_with_annotation": bool(evidence_gold and gold and evidence_gold != gold),
                   "training_label_ready": gold is not None,
                   "gold_evidence_evaluation_ready": bool(evidence_texts) and not invalid_refs,
                   "legacy_v2_gold": old_gold,
                   "original_annotations": [{k: v for k, v in a.items()} for a in matches],
                   "source_commit": actual_commit, "source_claim_file": f"Data/multivers-format/claims-{split.lower()}.jsonl"}
            normalized.append(row)
            models.append({"id": str(claim["id"]), "sample_id": sample_id, "claim": claim["claim"],
                           "cited_doc_ids": claim["cited_doc_ids"], "evidence": evidence_converted,
                           "gold": gold, "evidence_missing": row["evidence_missing"],
                           "annotation_alignment_status": status, "training_label_ready": row["training_label_ready"]})
            if status != "unique" or invalid_refs or row["evidence_label_disagrees_with_annotation"]:
                review_rows.append({"sample_id": sample_id, "reason": status if status != "unique" else "evidence_reference_or_label_discrepancy",
                                    "raw_labels": raw_labels, "annotation_paths": row["annotation_paths"],
                                    "citing_pmcid_candidates": citing_ids, "project_label": gold,
                                    "evidence_derived_project_label": evidence_gold, "evidence_reference_errors": invalid_refs})
            if old_gold is not None and old_gold != gold:
                old_match = legacy_first_context_match(claim["claim"], annotation_order[split])
                reason = "legacy_no_match_etiquette_default" if old_match is None else "legacy_first_substring_picked_different_source" if old_match["annotation_path"] not in row["annotation_paths"] else "frozen_label_disagrees_with_original"
                legacy_differences.append({"sample_id": sample_id, "old_gold": old_gold, "new_gold": gold,
                                           "raw_label": raw_label, "alignment_status": status,
                                           "evidence_derived_project_label": evidence_gold,
                                           "annotation_paths": row["annotation_paths"], "difference_reason": reason,
                                           "legacy_matched_annotation_path": old_match["annotation_path"] if old_match else None,
                                           "legacy_matched_raw_label": old_match["label"] if old_match else None,
                                           "legacy_matched_first_context": ((old_match.get("citation_context") or [{}])[0].get("text")) if old_match else None})
        dump_jsonl(out / f"claims-{split.lower()}.jsonl", normalized)
        dump_jsonl(out / f"claims-{split.lower()}-model.jsonl", models)
        dump_csv(out / f"gold_mapping-{split.lower()}.csv",
                 [{"claim_id": r["id"], "raw_label": r["raw_label"], "project_label": r["gold"]} for r in normalized],
                 ["claim_id", "raw_label", "project_label"])
        all_records.extend(normalized)
        split_stats[split.lower()] = {"claim_count": len(normalized),
            "project_labels": counts(r["gold"] for r in normalized),
            "raw_labels": counts(r["raw_label"] for r in normalized),
            "alignment_status": dict(collections.Counter(r["annotation_alignment_status"] for r in normalized)),
            "evidence_missing": sum(r["evidence_missing"] for r in normalized),
            "evidence_missing_by_project_label": counts(r["gold"] for r in normalized if r["evidence_missing"]),
            "missing_conversion_despite_annotated_segments": sum(r["evidence_missing_reason"] == "conversion_did_not_locate_annotated_segments" for r in normalized),
            "invalid_evidence_references": sum(bool(r["evidence_reference_errors"]) for r in normalized),
            "reference_paper_groups": len({r["cited_reference_group_id"] for r in normalized}),
            "label_disagreements_with_original_evidence": sum(r["evidence_label_disagrees_with_annotation"] for r in normalized)}
    dump_csv(out / "alignment_review.csv", review_rows, ["sample_id", "reason", "raw_labels", "project_label", "evidence_derived_project_label", "annotation_paths", "citing_pmcid_candidates", "evidence_reference_errors"])
    dump_csv(out / "legacy_v2_label_differences.csv", legacy_differences, ["sample_id", "old_gold", "new_gold", "raw_label", "alignment_status", "evidence_derived_project_label", "annotation_paths", "difference_reason", "legacy_matched_annotation_path", "legacy_matched_raw_label", "legacy_matched_first_context"])
    missing_rows = [{k: r[k] for k in ["sample_id", "raw_label", "project_label", "evidence_status", "evidence_missing_reason", "annotation_paths"]} for r in all_records if r["evidence_missing"]]
    dump_csv(out / "missing_gold_evidence.csv", missing_rows, ["sample_id", "raw_label", "project_label", "evidence_status", "evidence_missing_reason", "annotation_paths"])
    groups = collections.defaultdict(lambda: collections.defaultdict(set))
    for row in all_records:
        groups["cited_pmcid"][row["cited_pmcid"]].add(row["split"])
        for citing in row["citing_pmcid_candidates"]:
            groups["citing_pmcid"][citing].add(row["split"])
        groups["strict_claim_text"][normalize(row["claim"])].add(row["split"])
    leakage_rows = [{"group_type": kind, "group_id": group, "splits": sorted(splits)}
                    for kind, values in groups.items() for group, splits in values.items() if len(splits) > 1]
    dump_csv(out / "cross_split_groups.csv", leakage_rows, ["group_type", "group_id", "splits"])
    # Corpus contains paragraph blocks, verified against references_sentence, not whole articles.
    audit = {"schema_version": SCHEMA_VERSION, "source_commit": actual_commit, "splits": split_stats,
             "total_claims": len(all_records), "total_project_labels": counts(r["gold"] for r in all_records),
             "corpus_records": len(corpus_rows), "corpus_sentences": sum(len(r["abstract"]) for r in corpus_rows),
             "corpus_unit": "paragraph_block", "reference_article_count": len(reference_groups),
             "corpus_original_reference_mapping_verified": len(corpus_map),
             "original_evidence_segments": len(segment_audit),
             "original_evidence_segment_location_status": counts(row["location_status"] for row in segment_audit),
             "cross_split_group_counts": {kind: sum(r["group_type"] == kind for r in leakage_rows) for kind in groups},
             "legacy_v2_differences": len(legacy_differences), "legacy_comparison_supplied": bool(args.legacy_dir),
             "legacy_source_manifest": legacy_manifest,
             "manual_alignment_review_rows": len(review_rows), "unresolved_project_labels": sum(r["gold"] is None for r in all_records),
             "context_identification_counts": {split.lower(): len(load_jsonl(data / f"{split.lower()}.jsonl")) for split in EXPECTED_COUNTS},
             "rules": ["Project label comes from matched original annotation, never from evidence absence.",
                       "Ambiguous source alternatives are retained, and conflicting labels stay null.",
                       "The published train/dev/test split stays unchanged; text/citing overlaps are reported.",
                       "Corpus doc_id identifies a paragraph block; paper grouping uses the reference archive mapping."]}
    dump_json(out / "audit_summary.json", audit)
    artifact_files = []
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "artifact_manifest.json":
            artifact_files.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())})
    dump_json(out / "artifact_manifest.json", {"schema_version": SCHEMA_VERSION, "source_commit": actual_commit, "files": artifact_files})
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    if audit["unresolved_project_labels"]:
        raise SystemExit("Some labels remain unresolved. They are preserved as null; exclude them from supervised training.")


if __name__ == "__main__":
    main()
