"""Input/gold loading, assistant-only padding, and strict three-label scoring.

Tracking IDs stay outside messages. Transformers, PEFT, and a GPU are not
required here; torch is imported only when collating a training batch.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

LABELS = ("ACCURATE", "NOT_ACCURATE", "IRRELEVANT")


def load_gold(path, split=None):
    """Read {claim_id,label} JSONL or legacy mapping/split CSV."""
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        if path.suffix.lower() == ".csv":
            rows = list(csv.DictReader(handle))
        else:
            rows = [json.loads(line) for line in handle if line.strip()]
    labels = {}
    for row in rows:
        if split is not None and row.get("split", split) != split:
            continue
        cid = str(row.get("claim_id", row.get("row_id", "")))
        label = row.get("label", row.get("project_label"))
        if not cid or label not in LABELS:
            raise ValueError(f"Invalid gold row in {path}: {row!r}")
        if cid in labels:
            raise ValueError(f"Duplicate gold ID: {cid}")
        labels[cid] = label
    if not labels:
        raise ValueError(f"Empty gold selection in {path}, split={split!r}")
    return labels


def load_records(path, labels, max_samples=None):
    """Validate the complete ID join before selecting a smoke subset."""
    path = Path(path)
    records, seen = [], set()
    with path.open(encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            cid = str(row["claim_id"])
            if cid in seen:
                raise ValueError(f"Duplicate input ID {cid} at {path}:{line_no}")
            if cid not in labels:
                raise ValueError(f"Input ID {cid} has no matching gold in this split")
            if not isinstance(row.get("system_prompt"), str) or not isinstance(row.get("user_prompt"), str):
                raise ValueError(f"Missing prompt at {path}:{line_no}")
            if not row["system_prompt"] or not row["user_prompt"]:
                raise ValueError(f"Empty prompt at {path}:{line_no}")
            seen.add(cid)
            records.append({**row, "claim_id": cid, "label": labels[cid], "gold": labels[cid]})
    missing = set(labels) - seen
    if missing:
        raise ValueError(f"Missing {len(missing)} gold IDs in inputs: {sorted(missing)[:5]}")
    if max_samples is not None:
        if max_samples < 1:
            raise ValueError("max_samples must be positive")
        records = records[:max_samples]
    return records


def encode_assistant_record(record, tokenizer, max_length):
    """Use character offsets to mask only assistant JSON and the turn end.

The actual chat template may insert an empty thinking block. Character offsets
avoid supervising that block or guessing the assistant start from a marker.
Overlength records fail visibly instead of losing evidence or the label.
"""
    answer = json.dumps({"label": record["label"]}, ensure_ascii=False)
    messages = [
        {"role": "system", "content": record["system_prompt"]},
        {"role": "user", "content": record["user_prompt"]},
        {"role": "assistant", "content": answer},
    ]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False, enable_thinking=False
    )
    start = text.rfind(answer)
    if start < 0:
        raise ValueError(f"Chat template did not preserve assistant JSON: {record['claim_id']}")
    end = start + len(answer)
    encoded = tokenizer(text, add_special_tokens=False, truncation=False, return_offsets_mapping=True)
    ids = list(encoded["input_ids"])
    if len(ids) > max_length:
        raise ValueError(f"claim_id={record['claim_id']} has {len(ids)} tokens > max_length={max_length}; no silent truncation")
    offsets = encoded.get("offset_mapping")
    if offsets is None or len(offsets) != len(ids):
        raise ValueError("A fast tokenizer with character offsets is required for assistant loss masking")
    targets, supervised = [-100] * len(ids), []
    for index, (left, right) in enumerate(offsets):
        if right > start and left < end:
            targets[index] = ids[index]
            supervised.append((left, right))
    if not supervised or min(x[0] for x in supervised) > start or max(x[1] for x in supervised) < end:
        raise ValueError(f"Assistant JSON target was not fully tokenized: {record['claim_id']}")
    last_target = max(i for i, value in enumerate(targets) if value != -100)
    eos_id = tokenizer.eos_token_id
    if eos_id is not None:
        for index in range(last_target + 1, len(ids)):
            if ids[index] == eos_id:
                targets[index] = ids[index]
                break
    return {"input_ids": ids, "labels": targets, "attention_mask": list(encoded["attention_mask"])}


@dataclass
class AssistantOnlyCollator:
    """Pad supplied labels with -100 without recreating the loss mask."""

    tokenizer: object

    def __call__(self, features):
        import torch

        if not features:
            raise ValueError("Cannot collate an empty batch")
        pad_id = self.tokenizer.pad_token_id
        if pad_id is None:
            raise ValueError("Set tokenizer.pad_token_id before collating")
        width = max(len(feature["input_ids"]) for feature in features)
        ids_all, masks_all, labels_all = [], [], []
        for feature in features:
            ids = list(feature["input_ids"])
            labels = list(feature["labels"])
            mask = list(feature.get("attention_mask", [1] * len(ids)))
            if len(ids) != len(labels) or len(ids) != len(mask):
                raise ValueError("input_ids, labels and attention_mask must have equal lengths")
            if not any(value != -100 for value in labels):
                raise ValueError("Training example has no supervised assistant tokens")
            for token, target, attended in zip(ids, labels, mask):
                if target != -100 and (target != token or not attended):
                    raise ValueError("Invalid assistant label or supervision on padding")
            pads = width - len(ids)
            if getattr(self.tokenizer, "padding_side", "right") == "left":
                ids, labels, mask = [pad_id] * pads + ids, [-100] * pads + labels, [0] * pads + mask
            else:
                ids, labels, mask = ids + [pad_id] * pads, labels + [-100] * pads, mask + [0] * pads
            ids_all.append(ids)
            labels_all.append(labels)
            masks_all.append(mask)
        return {
            "input_ids": torch.tensor(ids_all, dtype=torch.long),
            "attention_mask": torch.tensor(masks_all, dtype=torch.long),
            "labels": torch.tensor(labels_all, dtype=torch.long),
        }


def parse_label(text):
    """Accept a whole JSON response or an exact bare label; never substrings."""
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].lower() in ("```", "```json"):
            text = "\n".join(lines[1:-1]).strip()
    if text in LABELS:
        return text
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return "INVALID"
    label = obj.get("label") if isinstance(obj, dict) else None
    return label if isinstance(label, str) and label in LABELS else "INVALID"


def compute_metrics(predictions, golds):
    """INVALID stays a false negative for its gold class, including Macro-F1."""
    if len(predictions) != len(golds):
        raise ValueError("Prediction and gold lengths differ")
    label2id = {label: index for index, label in enumerate(LABELS)}
    confusion = [[0] * len(LABELS) for _ in LABELS]
    invalid_by_gold = {label: 0 for label in LABELS}
    for pred, gold in zip(predictions, golds):
        if gold not in label2id:
            raise ValueError(f"Invalid gold label: {gold!r}")
        if pred not in label2id:
            invalid_by_gold[gold] += 1
        else:
            confusion[label2id[gold]][label2id[pred]] += 1
    per_class, scores = {}, []
    for i, label in enumerate(LABELS):
        tp = confusion[i][i]
        fp = sum(row[i] for row in confusion) - tp
        fn = sum(confusion[i]) - tp + invalid_by_gold[label]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
        scores.append(f1)
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn,
                            "tp": tp, "fp": fp, "fn": fn, "invalid_count": invalid_by_gold[label]}
    correct = sum(confusion[i][i] for i in range(len(LABELS)))
    total = len(golds)
    return {"accuracy": correct / total if total else 0.0, "macro_f1": sum(scores) / len(LABELS),
            "per_class": per_class, "confusion_matrix": confusion, "invalid_by_gold": invalid_by_gold,
            "invalid_count": sum(invalid_by_gold.values()), "total": total, "correct": correct,
            "label_order": list(LABELS), "invalid_policy": "count as false negative of gold class; included in total"}
