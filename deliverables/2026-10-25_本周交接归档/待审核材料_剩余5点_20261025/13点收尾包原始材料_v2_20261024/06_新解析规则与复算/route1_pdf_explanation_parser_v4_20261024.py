"""Versioned explanation parser with source mappings; no inference or semantics."""
from __future__ import annotations

import hashlib
import json

from pdf_quote_mapping_trial_v1 import match_quote, unwrap_outer_json_fence
from route1_pdf_pipeline_v3 import strict_json

VERSION = "route1_pdf_explanation_parser_v4_20261024"
LINE_JOIN_WHITELIST = (
    ("973971a504490433db97e905e8cd9d632150f03bcc746ffebe1c29108d7c0736", 5,
     "e3a33edf965cafef323d619e4b2c6f454f36441e0fe6b4ab41ec9c9c32c48f19", 1810, 1812),
    ("973971a504490433db97e905e8cd9d632150f03bcc746ffebe1c29108d7c0736", 5,
     "e3a33edf965cafef323d619e4b2c6f454f36441e0fe6b4ab41ec9c9c32c48f19", 1904, 1906),
    ("807123749aadd095c88f3a976d29834673fa2fc61cdf5b7aadc0e1514075b485", 1,
     "ea935cc98fdb6b5b449d80e7e38ded2ed4f5f0122c55794ba3b51f7e24d69eb4", 3935, 3937),
)


def require(value, message):
    if not value:
        raise ValueError(message)


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def policy():
    return {
        "version": VERSION,
        "complete_single_outer_json_fence": True,
        "whitespace_word_boundaries_preserved": True,
        "exact_match_precedence": True,
        "case_number_punctuation_negation_changes_allowed": False,
        "incomplete_json_repair_allowed": False,
        "soft_hyphen_handling": "Only existing layout matcher ASCII-letter gaps, with source map",
        "line_end_hyphen_removal": "Only three PDF/page/candidate-hash/character-interval entries",
        "line_join_whitelist": [list(item) for item in LINE_JOIN_WHITELIST],
        "scope": "New engineering parser candidate; original strict results preserved",
        "human_confirmation_inferred": False,
        "semantic_acceptance_inferred": False,
    }


def policy_sha256():
    return text_sha(json.dumps(policy(), sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def candidate_fields(candidate):
    require(isinstance(candidate, dict), "invalid_candidate")
    raw, model = candidate["raw_text"], candidate["model_text"]
    require(isinstance(raw, str) and isinstance(model, str), "invalid_candidate_text")
    require(raw == model, "candidate_transcription_patch_needs_separate_review")
    # This revision is deliberately scoped to the remaining13, whose candidates
    # have no model/raw transcription differences. Earlier glyph patches retain
    # their own parser and policy; do not silently apply them here.
    require(text_sha(raw) == candidate["raw_text_sha256"] and text_sha(model) == candidate["model_text_sha256"], "candidate_text_hash_mismatch")
    fragments = candidate["pdf_fragments"]
    require(isinstance(fragments, list) and len(fragments) == 1, "single_candidate_fragment_required")
    fragment = fragments[0]
    require(fragment["raw_text"] == raw and text_sha(fragment["raw_text"]) == fragment["raw_text_sha256"], "candidate_fragment_mismatch")
    require(fragment["char_end_exclusive"] - fragment["char_start"] == len(raw), "candidate_fragment_length_mismatch")
    return raw, model, fragment


def parse_explanation(raw_output, candidates):
    operations = []
    try:
        require(isinstance(raw_output, str), "invalid_raw_output_type")
        body, unwrapped = unwrap_outer_json_fence(raw_output)
        if unwrapped:
            operations.append("one_complete_outer_json_fence_removed")
        elif raw_output.lstrip().startswith("```"):
            raise ValueError("incomplete_or_invalid_outer_json_fence")
        obj = strict_json(body)
        if obj == {"failure_status": "insufficient_evidence"}:
            return {"version": VERSION, "status": "insufficient_evidence", "evidence_ids": [],
                    "reason_unreviewed": None, "quote_locators": [], "operations": operations,
                    "semantic_verified": False, "human_reviewed": False}
        require(set(obj) == {"evidence_ids", "quotes", "reason"}, "wrong_explanation_fields")
        ids = obj["evidence_ids"]
        require(isinstance(ids, list) and ids and all(isinstance(i, str) for i in ids) and len(ids) == len(set(ids)), "invalid_or_duplicate_evidence_ids")
        require(isinstance(candidates, list), "invalid_candidates")
        available = {candidate["evidence_id"]: candidate for candidate in candidates}
        require(len(available) == len(candidates), "duplicate_candidate_ids")
        require(set(ids) <= set(available), "evidence_id_out_of_range")
        require(isinstance(obj["reason"], str) and obj["reason"].strip(), "missing_reason")
        require(isinstance(obj["quotes"], list) and obj["quotes"], "missing_quotes")
        locators, covered, joins = [], set(), []
        for quote in obj["quotes"]:
            require(isinstance(quote, dict) and set(quote) == {"evidence_id", "quote"}, "invalid_quote_fields")
            eid, text = quote["evidence_id"], quote["quote"]
            require(isinstance(eid, str) and eid in ids and isinstance(text, str) and text.strip(), "invalid_quote_or_id")
            candidate = available[eid]
            raw, model, fragment = candidate_fields(candidate)
            result = match_quote(model, text)
            require(result["unique_mapping"] and len(result["matches"]) == 1, "quote_not_uniquely_mappable")
            match = result["matches"][0]
            changes, whitelist_used = [], []
            for change in match["transformations"]:
                absolute_start = fragment["char_start"] + change["source_start"]
                absolute_end = fragment["char_start"] + change["source_end"]
                require(raw[change["source_start"]:change["source_end"]] == change["raw"], "transformation_source_mismatch")
                if change["kind"] == "line_end_hyphen_join_hypothesis":
                    entry = (candidate["source_pdf_sha256"], fragment["pdf_page"], candidate["model_text_sha256"], absolute_start, absolute_end)
                    require(entry in LINE_JOIN_WHITELIST and change["raw"] == "-\n", "line_end_join_not_whitelisted")
                    whitelist_used.append(list(entry))
                else:
                    require(change["kind"] in {"whitespace_fold", "soft_hyphen_removed", "line_break_after_retained_hyphen"}, "unreviewed_transformation")
                changes.append({**change, "page_char_start": absolute_start, "page_char_end_exclusive": absolute_end})
            start, end = match["source_start"], match["source_end"]
            excerpt = raw[start:end]
            character_map = [{"quote_start": unit["quote_start"], "quote_end": unit["quote_end"],
                              "page_char_start": fragment["char_start"] + unit["source_start"],
                              "page_char_end_exclusive": fragment["char_start"] + unit["source_end"]} for unit in match["character_map"]]
            locators.append({"evidence_id": eid, "model_quote_unchanged": text,
                             "raw_source_excerpt": excerpt, "raw_source_excerpt_sha256": text_sha(excerpt),
                             "source_pdf_sha256": candidate["source_pdf_sha256"], "pdf_page": fragment["pdf_page"],
                             "char_start": fragment["char_start"] + start, "char_end_exclusive": fragment["char_start"] + end,
                             "source_blocks": fragment["source_blocks"], "bbox_scope": fragment["bbox_scope"],
                             "offset_basis": fragment["offset_basis"], "character_map": character_map,
                             "layout_operations": changes, "line_join_whitelist_used": whitelist_used,
                             "human_mapping_confirmed": None})
            covered.add(eid)
            joins.extend(whitelist_used)
        require(covered == set(ids), "selected_evidence_has_no_quote")
        return {"version": VERSION, "status": "structure_and_source_mapping_valid_pending_human_semantics",
                "evidence_ids": ids, "reason_unreviewed": obj["reason"], "quote_locators": locators,
                "operations": operations, "line_join_whitelist_used": joins,
                "semantic_verified": False, "human_reviewed": False, "formal_end_to_end_accepted": False}
    except (ValueError, TypeError, KeyError) as error:
        return {"version": VERSION, "status": "invalid_explanation_output", "validation_error": str(error),
                "evidence_ids": [], "reason_unreviewed": None, "quote_locators": [], "operations": operations,
                "semantic_verified": False, "human_reviewed": False}
