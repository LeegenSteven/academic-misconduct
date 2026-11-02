"""Portable execution handoff; frozen two-point inference code stays unchanged."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "results/route1_qwen38_v3/2026-10-25/pdf_demo/supplement_official_freeze_20261029"
MODEL = Path("/home/admire/models/Qwen3.8-27B")
ADAPTER = Path("/home/admire/citation_integrity_member2/incoming/quality_v1_20261009/cmj_sarol_mbio_full_memopt_trial_20261017_gpu2/train/checkpoint-100")
RUN = ROOT / "run01"
MIN_FREE_MIB = 35000  # Existing frozen backend guard, not a new memory policy.


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def verify_bundle():
    manifest = read(ROOT / "handoff_manifest.json")
    for name, expected in manifest["files_sha256"].items():
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT.resolve()), "Package path escapes its root")
        require(path.is_file() and sha(path) == expected, f"Package file differs: {name}")
    plan = read(PKG / "two_point_runtime_plan.json")
    items = [json.loads(line) for line in (PKG / "prepared_items.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    require(len(items) == 2 and [x["case_id"] for x in items] == plan["selected_case_ids"], "Wrong two-point scope")
    require(plan["prepared_items_sha256"] == sha(PKG / "prepared_items.jsonl"), "Prepared input differs")
    require(plan["runner_sha256"] == sha(PKG / "run_two_point_a100_20261029.py"), "Frozen runner differs")
    print(f"BUNDLE_VERIFIED files={len(manifest['files_sha256'])} frozen_points=2", flush=True)
    return manifest


def prepare():
    manifest = verify_bundle()
    template = MODEL / "chat_template.jinja"
    template_expected = manifest["base_files_sha256"]["chat_template.jinja"]
    if template.exists():
        require(sha(template) == template_expected, "Existing model template differs; it was not overwritten")
    else:
        # Exclusive creation: never replace a model file or follow a dangling link.
        with template.open("xb") as target, (ROOT / "official/chat_template.jinja").open("rb") as source:
            shutil.copyfileobj(source, target)
        print("OFFICIAL_MISSING_TEMPLATE_ADDED", flush=True)
    for name, expected in manifest["base_files_sha256"].items():
        require((MODEL / name).is_file() and sha(MODEL / name) == expected, f"Official model/tokenizer differs: {name}")
        print(f"OFFICIAL_FILE_OK {name}", flush=True)
    for name, expected in manifest["adapter_files_sha256"].items():
        require((ADAPTER / name).is_file() and sha(ADAPTER / name) == expected, f"Mbio checkpoint-100 differs: {name}")
    require(sha(ROOT / "official/18_shards_expected_sha256.txt") == manifest["official_weights_manifest_sha256"], "Weight list differs")
    require((MODEL / "model.safetensors.index.json").is_file(), "Weight index missing")
    for i in range(1, 19):
        require((MODEL / f"model-{i:05d}-of-00018.safetensors").is_file(), f"Weight shard missing: {i}")
    versions = {name: importlib.metadata.version(name) for name in ("torch", "transformers", "peft", "accelerate", "bitsandbytes")}
    require(versions["transformers"] == "5.8.0", "Existing backend requires transformers 5.8.0")
    result = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.free,utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True, timeout=20)
    inventory = []
    for line in result.stdout.splitlines():
        index, free, utilization = [x.strip() for x in line.split(",")]
        inventory.append({"gpu": index, "free_mib": int(free), "utilization": int(utilization)})
    require(inventory, "No GPU inventory")
    print(json.dumps({"versions": versions, "gpus": inventory, "frozen_backend_min_free_mib": MIN_FREE_MIB, "model_loaded": False}, ensure_ascii=False), flush=True)
    return manifest, inventory


def launch(gpu):
    manifest, inventory = prepare()
    require(not RUN.exists(), "run01 already exists. Preserve it; use status/collect, never relaunch automatically")
    candidates = inventory if gpu == "auto" else [x for x in inventory if x["gpu"] == gpu]
    require(candidates, f"GPU not found: {gpu}")
    chosen = max(candidates, key=lambda x: x["free_mib"])
    require(chosen["free_mib"] >= MIN_FREE_MIB, f"Existing frozen backend requires {MIN_FREE_MIB} MiB free; best selected GPU has {chosen['free_mib']} MiB. No model started; do not stop other jobs")
    RUN.mkdir()  # Atomic duplicate-launch guard.
    request = {"requested_at_utc": now(), "operator": "LiYun", "gpu": chosen, "package_files_sha256": manifest["files_sha256"], "two_point_plan_sha256": sha(PKG / "two_point_runtime_plan.json"), "scope": "two frozen PDF supplements; original 18 reused; no training or Test", "automatic_retry": False}
    write(RUN / "execution_request.json", request)
    try:
        with (RUN / "orchestrator.run.log").open("x", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "worker", "--gpu", chosen["gpu"]], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    except Exception as error:
        write(RUN / "completion.json", {"finished_at_utc": now(), "status": "launch_failed", "error": str(error)})
        raise
    write(RUN / "launch_receipt.json", {"pid": process.pid, "gpu": chosen["gpu"], "started_at_utc": now()})
    print(f"TWO_POINT_PID={process.pid}\nGPU={chosen['gpu']}\nRUN_DIR={RUN}\nBACKGROUND_STARTED", flush=True)


def worker(gpu):
    require(RUN.is_dir() and (RUN / "execution_request.json").is_file(), "Missing explicit launch request")
    stage_results = []
    try:
        verify_bundle()
        for stage in ("classifier", "explainer"):
            print(f"STAGE_START {stage}", flush=True)
            command = [sys.executable, "-u", str(PKG / "run_two_point_a100_20261029.py"), stage, "--model-path", str(MODEL), "--weights-manifest", str(ROOT / "official/18_shards_expected_sha256.txt"), "--gpu", gpu, "--operator", "LiYun", "--output", str(RUN / stage)]
            if stage == "classifier":
                command += ["--adapter", str(ADAPTER)]
            result = subprocess.run(command, cwd=ROOT, check=False)
            stage_results.append({"stage": stage, "exit_code": result.returncode})
            print(f"STAGE_END {stage} exit_code={result.returncode}", flush=True)
            if result.returncode:
                break
        status = "completed" if len(stage_results) == 2 and all(x["exit_code"] == 0 for x in stage_results) else "failed_no_retry"
        write(RUN / "completion.json", {"finished_at_utc": now(), "status": status, "stages": stage_results, "human_semantic_acceptance": False})
    except Exception as error:
        write(RUN / "completion.json", {"finished_at_utc": now(), "status": "failed_no_retry", "stages": stage_results, "error": str(error)})
        raise


def status():
    if not RUN.exists():
        print("NOT_STARTED")
        return
    if (RUN / "completion.json").exists():
        print(json.dumps(read(RUN / "completion.json"), ensure_ascii=False, indent=2))
    else:
        print("NO_COMPLETION_RECEIPT; inspect orchestrator/stage logs; no automatic restart")
    for stage in ("classifier", "explainer"):
        directory = RUN / stage
        response = directory / "responses.jsonl"
        # The worker may currently be appending a JSON line; count flushed lines only.
        lines = response.read_text(encoding="utf-8").splitlines(keepends=True) if response.exists() else []
        rows = [json.loads(x) for x in lines if x.endswith("\n") and x.strip()]
        counts = dict(Counter(x.get("parsed", {}).get("status", "unknown") for x in rows))
        code = (directory / "exit_code.txt").read_text().strip() if (directory / "exit_code.txt").exists() else "pending"
        print(json.dumps({"stage": stage, "responses": len(rows), "expected": 2, "parsed_statuses": counts, "exit_code": code}, ensure_ascii=False))
        log = directory / "run.log"
        if log.exists():
            print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-5:]))


def collect():
    require((RUN / "completion.json").is_file(), "No completion receipt; check status before collecting")
    archive = ROOT.parent / (ROOT.name + "_return.tar.gz")
    require(not archive.exists(), f"Return archive already exists; preserve it: {archive}")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(RUN, arcname="run01")
        tar.add(ROOT / "handoff_manifest.json", arcname="handoff_manifest.json")
        for name in ("freeze_receipt.json", "two_point_runtime_plan.json", "prepared_items.jsonl", "classification.inputs.jsonl", "explanation.inputs.jsonl"):
            tar.add(PKG / name, arcname="frozen_inputs/" + name)
    digest = sha(archive)
    archive.with_name(archive.name + ".sha256").write_text(digest + "  " + archive.name + "\n", encoding="utf-8", newline="\n")
    print(f"RETURN_ARCHIVE={archive}\nSHA256={digest}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("verify", "prepare", "launch", "status", "collect", "worker"))
    parser.add_argument("--gpu", default="auto")
    args = parser.parse_args()
    if args.action == "verify": verify_bundle()
    elif args.action == "prepare": prepare()
    elif args.action == "launch": launch(args.gpu)
    elif args.action == "worker": worker(args.gpu)
    elif args.action == "status": status()
    else: collect()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"HANDOFF_STOPPED {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
