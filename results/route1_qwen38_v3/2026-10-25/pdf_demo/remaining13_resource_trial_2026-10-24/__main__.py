"""Explicit resource trial for the already released remaining 13 PDF points."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
import traceback
import types
import zipfile

VERSION = "route1_pdf_remaining13_resource_trial_20261024"
MIB = 1024 * 1024
RELEASE_SHA = "09a875e7d8bcae223e39e1ba1c903c99405b17f8c08a8f3797e49dacb01106ec"
BACKEND_SHA = "800e2f1db364ba955fdcbecf26740fb3e3ae2e585a04ea18670f09a72b108caf"
OLD_GUARD = '        contract.require(free // (1024 * 1024) >= 35000, "Less than 35000 MiB free; stop before model loading")'
NEW_GUARD = '''        allocator_budget = min(free - 2048 * 1024 * 1024, int(total * 0.95))
        contract.require(allocator_budget > 0, "No allocator budget remains after 2048 MiB headroom")
        torch.cuda.set_per_process_memory_fraction(allocator_budget / total, 0)
        self.execution_resource_policy = {
            "version": "route1_pdf_remaining13_resource_trial_20261024",
            "old_35000_mib_launch_guard_applied": False,
            "headroom_mib": 2048,
            "free_before_load_bytes": free,
            "total_bytes": total,
            "pytorch_allocator_budget_bytes": allocator_budget,
            "pytorch_allocator_fraction": allocator_budget / total,
            "allocator_cap_covers_all_external_cuda_allocations": False,
            "shared_gpu_performance_isolation_guaranteed": False,
            "automatic_retry": False,
        }
        print("RESOURCE_TRIAL_POLICY " + json.dumps(self.execution_resource_policy, sort_keys=True), flush=True)'''


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def transform_backend(raw):
    require(hashlib.sha256(raw).hexdigest() == BACKEND_SHA, "Original backend changed")
    source = raw.decode("utf-8-sig")
    require(source.count(OLD_GUARD) == 1, "Resource guard patch is not unique")
    revised = source.replace(OLD_GUARD, NEW_GUARD)
    # Verify the only AST change is the explicitly described resource guard.
    original_tree = ast.parse(source)
    expected_tree = ast.parse(source.replace(OLD_GUARD, NEW_GUARD))
    require(ast.dump(ast.parse(revised)) == ast.dump(expected_tree), "Unexpected backend change")
    old_generate = next(n for n in ast.walk(original_tree) if isinstance(n, ast.FunctionDef) and n.name == "generate")
    new_generate = next(n for n in ast.walk(expected_tree) if isinstance(n, ast.FunctionDef) and n.name == "generate")
    require(ast.dump(old_generate) == ast.dump(new_generate), "Generation path changed")
    compile(revised, "<explicit_remaining13_resource_trial>", "exec")
    return revised


def own_files(package):
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("package_manifest.json"))
        require(archive.testzip() is None, "Package CRC failed")
        require(len(archive.namelist()) == len(set(archive.namelist())) and set(archive.namelist()) == set(manifest["files"]) | {"package_manifest.json"}, "Package file set changed")
        for name, expected in manifest["files"].items():
            require(hashlib.sha256(archive.read(name)).hexdigest() == expected, "Package file changed: " + name)
        return json.loads(archive.read("resource_policy.json")), json.loads(archive.read("expected_code_hashes.json"))


def verify_server(args, expected):
    require(sha(args.release) == RELEASE_SHA, "Use the recorded 13-point r2 A100 release")
    code = args.root / "code/ly"
    for name, expected_sha in expected.items():
        require(sha(code / name) == expected_sha, "Frozen source changed: " + name)
    released = read(args.release)
    require(len(released["selected_case_ids"]) == len(set(released["selected_case_ids"])) == 13 and released["fixed_denominator"] == 20, "Selected point set differs")
    require(released["runtime_plan"]["code_sha256"] == expected, "Frozen code manifest differs")
    require(not args.stage == "explainer" or args.adapter is None, "Explainer must not load an adapter")
    return code


def run(args, package, policy, expected):
    code = verify_server(args, expected)
    stage_dir = args.output_root / args.stage
    require(not stage_dir.exists(), "Stage output exists; do not overwrite or retry")
    args.output_root.mkdir(parents=True, exist_ok=True)
    request_path = args.output_root / (args.stage + "_execution_request.json")
    require(not request_path.exists(), "Execution request exists; preserve the prior attempt")
    raw = (code / "route1_pdf_hf_backend_v3.py").read_bytes()
    effective = transform_backend(raw)
    effective_sha = hashlib.sha256(effective.encode("utf-8")).hexdigest()
    write(args.output_root / (args.stage + "_effective_backend.py.txt"), {"original_sha256": BACKEND_SHA, "effective_sha256": effective_sha, "source": effective})
    request = {"version": VERSION, "recorded_at_utc": now(), "stage": args.stage,
               "gpu": args.gpu, "operator": "李云", "resource_policy": policy,
               "release_sha256": RELEASE_SHA, "package_sha256": sha(package),
               "original_backend_sha256": BACKEND_SHA, "effective_backend_sha256": effective_sha,
               "original_files_modified": False, "test_run": False, "training_run": False,
               "new_human_labels": 0, "semantic_acceptance_inferred": False}
    write(request_path, request)
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false", PYTHONDONTWRITEBYTECODE="1", CUDA_VISIBLE_DEVICES=args.gpu)
    sys.path.insert(0, str(code))
    import route1_pdf_remaining13_runtime_20261024 as runtime
    runtime.install()
    contract = runtime.base
    module = types.ModuleType("remaining13_explicit_resource_backend")
    module.__file__ = str(code / "route1_pdf_hf_backend_v3.py") + "[" + VERSION + "]"
    exec(compile(effective, module.__file__, "exec"), module.__dict__)

    def factory(stage, plan):
        backend = module.HFBackend(stage, plan, args.model_path, args.adapter, args.weights_manifest, args.gpu, "李云")
        backend.identity.update(execution_resource_revision=backend.execution_resource_policy,
                                original_backend_sha256=BACKEND_SHA, effective_backend_sha256=effective_sha,
                                execution_package_sha256=sha(package))
        return backend

    print("REMAINING13_RESOURCE_TRIAL_START stage=" + args.stage + " gpu=" + args.gpu + " selected=13 fixed_denominator=20", flush=True)
    try:
        metadata = contract.run_stage(args.stage, args.source_root, args.prepared_dir, args.release,
                                      stage_dir, runtime.gate.import_pdf(args.pymupdf_dir), factory)
        metadata["execution_resource_revision"] = request
        contract.write_json(stage_dir / "run_metadata.json", metadata)
        result = {"version": VERSION, "stage": args.stage, "status": metadata["status"], "exit_code": metadata["exit_code"],
                  "finished_at_utc": now(), "stage_directory": str(stage_dir), "formal_acceptances_added": 0}
        write(args.output_root / (args.stage + "_launch_summary.json"), result)
        print("REMAINING13_RESOURCE_TRIAL_END " + json.dumps(result, ensure_ascii=False), flush=True)
        return metadata["exit_code"]
    finally:
        for name, expected_sha in expected.items():
            require(sha(code / name) == expected_sha, "Original file changed during run: " + name)


def launch(args, package):
    require(not (args.output_root / args.stage).exists(), "Stage output exists; do not relaunch")
    log = Path.home() / (VERSION + "_" + args.stage + "_run01.run.log")
    receipt = log.with_suffix(".launch.json")
    require(not log.exists() and not receipt.exists(), "Launch log exists; inspect the prior attempt first")
    command = ["nohup", sys.executable, "-u", str(package), "--run", "--stage", args.stage, "--gpu", args.gpu,
               "--root", str(args.root), "--release", str(args.release), "--output-root", str(args.output_root),
               "--source-root", str(args.source_root), "--prepared-dir", str(args.prepared_dir),
               "--model-path", str(args.model_path), "--weights-manifest", str(args.weights_manifest), "--pymupdf-dir", str(args.pymupdf_dir)]
    if args.adapter is not None:
        command.extend(["--adapter", str(args.adapter)])
    with log.open("xb") as output:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    write(receipt, {"version": VERSION, "created_at_utc": now(), "pid": process.pid,
                    "command": command, "package_sha256": sha(package), "log": str(log),
                    "meaning": "Process launched; not a completed model run or acceptance"})
    print("REMAINING13_PID=" + str(process.pid))
    print("RUN_LOG=" + str(log))
    print("STAGE_LOG=" + str(args.output_root / args.stage / "run.log"))


def main():
    home = Path.home()
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--launch", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--stage", choices=("classifier", "explainer"), default="classifier")
    parser.add_argument("--gpu", default="2")
    parser.add_argument("--root", type=Path, default=home / "route1_pdf_remaining13_r2_20261024")
    parser.add_argument("--release", type=Path, default=home / "route1_pdf_remaining13_r2_release_20261024/release.json")
    parser.add_argument("--source-root", type=Path, default=home / "route1_pdf_cpu_migration_20261021/source")
    parser.add_argument("--prepared-dir", type=Path)
    parser.add_argument("--output-root", type=Path, default=home / "citation_integrity_member2/incoming/quality_v1_20261009/route1_pdf_remaining13_r2_resource_trial_20261024_run01")
    parser.add_argument("--model-path", type=Path, default=home / "route1_pdf_model_view_20261021")
    parser.add_argument("--weights-manifest", type=Path, default=home / "citation_integrity_member2/incoming/quality_v1_20261009/cmj_model_weightcheck_20261016/official_sha256sums.txt")
    parser.add_argument("--pymupdf-dir", type=Path, default=home / "route1_pdf_cpu_deps_20261021")
    parser.add_argument("--adapter", type=Path)
    args = parser.parse_args()
    package = Path(sys.argv[0]).resolve()
    policy, expected = own_files(package)
    require(args.gpu.isdigit(), "Select one physical GPU index")
    if args.verify_only:
        print("RESOURCE_TRIAL_PACKAGE_VERIFIED model_loaded=false GPU_used=false")
        return 0
    if args.prepared_dir is None:
        args.prepared_dir = args.root / "results/route1_qwen38_v3/2026-10-25/pdf_demo/remaining13_preparation_r2_2026-10-24"
    if args.stage == "classifier" and args.adapter is None:
        args.adapter = home / "citation_integrity_member2/incoming/quality_v1_20261009/cmj_sarol_mbio_full_memopt_trial_20261017_gpu2/train/checkpoint-100"
    verify_server(args, expected)
    if args.launch:
        launch(args, package)
        return 0
    return run(args, package, policy, expected)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
