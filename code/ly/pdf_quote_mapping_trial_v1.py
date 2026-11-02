"""Conservative quote-to-source mapping for a separate offline diagnostic."""
from __future__ import annotations
import re
import string

VERSION = "route1_pdf_quote_mapping_trial_v1_20261023"
LETTERS = frozenset(string.ascii_letters)


def quote_units(quote):
    return [(" " if m.group().isspace() else m.group(), m.start(), m.end())
            for m in re.finditer(r"\s+|\S", quote)]


def unwrap_outer_json_fence(raw):
    fence = chr(96) * 3
    m = re.fullmatch(r"\s*" + fence + r"json[ \t]*\r?\n([\s\S]*?)\r?\n" + fence + r"[ \t]*\s*", raw)
    return (m.group(1), True) if m else (raw, False)


def match_quote(source, quote):
    """Return mappings, never acceptance. Offsets are Unicode half-open.

    Prefer exact matches and count overlapping occurrences. Layout-only matching
    preserves word boundaries, case, numbers, punctuation and lexical hyphens.
    ASCII line-end hyphen removal is a hypothesis requiring review.
    """
    if not isinstance(source, str) or not isinstance(quote, str) or not quote.strip():
        raise ValueError("Empty/non-string quote")
    exact = list(re.finditer(r"(?=" + re.escape(quote) + r")", source))
    if exact:
        matches = []
        for m in exact:
            matches.append({
                "source_start": m.start(), "source_end": m.start() + len(quote),
                "raw_source_excerpt": source[m.start():m.start() + len(quote)],
                "character_map": [{"quote_start": i, "quote_end": i + 1,
                                  "source_start": m.start() + i, "source_end": m.start() + i + 1}
                                 for i in range(len(quote))],
                "transformations": [], "line_join_review_required": False,
            })
        return {"status": "exact_unique" if len(matches) == 1 else "ambiguous",
                "match_count": len(matches), "matches": matches,
                "unique_mapping": len(matches) == 1, "line_join_review_required": False}

    units = quote_units(quote)
    expression = []
    for i, (character, _, _) in enumerate(units):
        if i:
            previous = units[i - 1][0]
            if previous in LETTERS and character in LETTERS:
                expression.append(r"(?:\u00ad|-[ \t]*\r?\n[ \t]*)*")
            elif previous == "-" and character in LETTERS:
                expression.append(r"(?:[ \t]*\r?\n[ \t]*)?")
        expression.append(f"(?P<c{i}>" + (r"\s+" if character == " " else re.escape(character)) + ")")
    pattern = re.compile(r"(?=(?P<whole>" + "".join(expression) + "))")
    matches = []
    for m in pattern.finditer(source):
        mapping, changes = [], []
        for i, (character, qstart, qend) in enumerate(units):
            start, end = m.span(f"c{i}")
            mapping.append({"quote_start": qstart, "quote_end": qend,
                            "source_start": start, "source_end": end})
            if character == " " and source[start:end] != quote[qstart:qend]:
                changes.append({"kind": "whitespace_fold", "source_start": start,
                                "source_end": end, "raw": source[start:end], "to": " "})
            if i:
                left = m.end(f"c{i-1}")
                gap = source[left:start]
                if gap and units[i - 1][0] == "-":
                    changes.append({"kind": "line_break_after_retained_hyphen",
                                    "source_start": left, "source_end": start, "raw": gap, "to": ""})
                elif gap:
                    for part in re.finditer(r"\u00ad|-[ \t]*\r?\n[ \t]*", gap):
                        raw = part.group()
                        changes.append({
                            "kind": "soft_hyphen_removed" if raw == "\u00ad" else "line_end_hyphen_join_hypothesis",
                            "source_start": left + part.start(), "source_end": left + part.end(),
                            "raw": raw, "to": "",
                        })
        start, end = m.span("whole")
        matches.append({
            "source_start": start, "source_end": end, "raw_source_excerpt": source[start:end],
            "character_map": mapping, "transformations": changes,
            "line_join_review_required": any(x["kind"] == "line_end_hyphen_join_hypothesis" for x in changes),
        })
    unique = len(matches) == 1
    needs_review = unique and matches[0]["line_join_review_required"]
    status = ("unique_mapping_line_join_review_required" if needs_review else "normalized_unique") if unique else (
        "ambiguous" if matches else "not_matched")
    return {"status": status, "match_count": len(matches), "matches": matches,
            "unique_mapping": unique, "line_join_review_required": bool(needs_review)}

