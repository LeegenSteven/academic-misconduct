"""Fetch the two seed=42 source snapshots without committing raw data.

The repository intentionally ignores data/raw/. This script downloads dated
snapshots, extracts only the SciFact files used by the audit, and writes a
manifest with URLs and SHA-256 hashes. Existing dated files are never replaced
unless --force is passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import time
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen


SCIFACT_URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
RED_DATA_URL = "https://raw.githubusercontent.com/tianmai-zhang/ReferenceErrorDetection/main/dataset/ReferenceErrorDetection_data.xlsx"
RED_LICENSE_URL = "https://raw.githubusercontent.com/tianmai-zhang/ReferenceErrorDetection/main/dataset/LICENSE.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def download(url: str, path: Path, force: bool) -> None:
    if path.exists() and not force:
        return
    request = Request(url, headers={"User-Agent": "academic-misconduct-repro/1.0"})
    with urlopen(request, timeout=60) as response, path.open("wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)
    time.sleep(1.0)


def extract_member(archive: Path, suffix: str, output: Path, force: bool) -> None:
    if output.exists() and not force:
        return
    with tarfile.open(archive, "r:gz") as bundle:
        candidates = [member for member in bundle.getmembers() if member.name.endswith(suffix)]
        if len(candidates) != 1:
            raise RuntimeError(f"expected one archive member ending {suffix!r}, found {len(candidates)}")
        source = bundle.extractfile(candidates[0])
        if source is None:
            raise RuntimeError(f"cannot read archive member {candidates[0].name}")
        output.write_bytes(source.read())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    raw = args.root / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    archive = raw / f"scifact_data_{args.date}.tar.gz"
    claims = raw / f"scifact_claims_dev_{args.date}.jsonl"
    corpus = raw / f"scifact_corpus_{args.date}.jsonl"
    red_data = raw / f"reference_error_detection_data_{args.date}.xlsx"
    red_license = raw / f"reference_error_detection_LICENSE_{args.date}.txt"

    download(SCIFACT_URL, archive, args.force)
    extract_member(archive, "claims_dev.jsonl", claims, args.force)
    extract_member(archive, "corpus.jsonl", corpus, args.force)
    download(RED_DATA_URL, red_data, args.force)
    download(RED_LICENSE_URL, red_license, args.force)

    manifest = {
        "date": args.date,
        "sources": {
            "SciFact": {"url": SCIFACT_URL, "files": {p.name: sha256(p) for p in (archive, claims, corpus)}},
            "ReferenceErrorDetection": {
                "data_url": RED_DATA_URL,
                "license_url": RED_LICENSE_URL,
                "files": {p.name: sha256(p) for p in (red_data, red_license)},
            },
        },
    }
    (raw / f"seed42_sources_manifest_{args.date}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
