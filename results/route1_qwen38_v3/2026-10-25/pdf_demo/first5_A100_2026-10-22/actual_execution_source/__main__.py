"""First5 execution resource revision; original scope release remains immutable."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os
from pathlib import Path, PurePosixPath
import subprocess, sys, traceback, zipfile
from datetime import datetime, timezone
VERSION="route1_pdf_first5_resource_v1_20261022"
ROOT=Path("/home/admire")
EXECUTION=ROOT/"route1_pdf_first5_resource_release_20261022"
EVIDENCE=ROOT/"route1_pdf_memory_preflight_20261022_r2_attempt1"
def require(ok,msg):
    if not ok:raise ValueError(msg)
def now():return datetime.now(timezone.utc).isoformat()
def encoded(x):return (json.dumps(x,ensure_ascii=False,indent=2)+"\n").encode()
def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def write(p,x):Path(p).write_bytes(encoded(x))
def package():
    with zipfile.ZipFile(Path(sys.argv[0]).resolve()) as z:
        m=json.loads(z.read("manifest.json"))
        require(m["version"]==VERSION,"Wrong execution resource package")
        names=z.namelist()
        require(len(names)==len(set(names)) and set(names)==set(m["files"])|{"manifest.json"},"Unexpected package member")
        for n,h in m["files"].items():
            p=PurePosixPath(n)
            require(not p.is_absolute() and ".." not in p.parts and ":" not in n and "\\" not in n,"Unsafe package path")
            require(hashlib.sha256(z.read(n)).hexdigest()==h,"Package member changed: "+n)
        policy=json.loads(z.read("policy.json"))
    print("EXECUTION_PACKAGE_VERIFIED files="+str(len(m["files"]))+" model_loaded=false",flush=True)
    return policy,m
def verify_environment_and_inputs(policy,cpu_tokens):
    # CPU tokenization can import torch in Transformers5.8; it must not initialize CUDA.
    if cpu_tokens:
        os.environ.update(CUDA_VISIBLE_DEVICES="",USE_TORCH="0",USE_TF="0",
                          HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1")
    import probe_contract as probe
    contract,reference,plan,keyed,specs=probe.prepare(policy["probe_policy"],cpu_tokens)
    require(contract.code_hashes()==policy["original_contract_code_sha256"],"Original contract files changed")
    expected=policy["memory_evidence_files"]
    require({str(p.relative_to(EVIDENCE)).replace("\\","/") for p in EVIDENCE.rglob("*") if p.is_file()}==set(expected),
            "Memory evidence file inventory differs")
    for n,h in expected.items():require(sha(EVIDENCE/n)==h,"A100 memory evidence differs: "+n)
    require(sha(ROOT/"route1_pdf_memory_preflight_v1r2_20261022.pyz")==policy["memory_probe_package_sha256"],
            "Memory probe package differs")
    for role in ("classifier","explainer"):
        require(specs[role]["stages"][role]==policy["longest_input_stage"][role],
                "Selected input now exceeds/differs from probed input")
    return probe,contract,plan,keyed
def execution_description(policy,manifest):
    return {"version":VERSION,"source_scope_release_sha256":policy["probe_policy"]["server_release_sha256"],
        "package_sha256":sha(Path(sys.argv[0]).resolve()),
        "execution_policy_sha256":hashlib.sha256(encoded(policy)).hexdigest(),
        "actual_backend_source_sha256":manifest["files"]["resource_backend.py"],
        "original_contract_code_sha256":policy["original_contract_code_sha256"],
        "selected_case_ids":policy["probe_policy"]["selected_case_ids"],
        "fixed_denominator":20,"settings":policy["frozen_settings"],
        "resource_change":policy["resource_change"],
        "memory_evidence_files":policy["memory_evidence_files"],
        "scope_approval_source":"Original first5 scope release; exact IDs, scopes and inputs preserved",
        "new_human_confirmation_created":False}
def validate_execution(policy,manifest):
    require((EXECUTION/"execution_release.json").is_file(),"Run --freeze first")
    actual=read(EXECUTION/"execution_release.json")
    expected=execution_description(policy,manifest)
    require(all(actual.get(k)==v for k,v in expected.items()),"Execution revision changed after freeze")
    return actual
def freeze(policy,manifest):
    require(not EXECUTION.exists(),"Execution revision exists; preserve existing release")
    probe,contract,plan,keyed=verify_environment_and_inputs(policy,True)
    require(plan["settings"]==policy["frozen_settings"],"Frozen inference settings differ")
    description=execution_description(policy,manifest)
    description.update(created_at_utc=now(),kind="supplemental_execution_resource_release",
                       original_scope_release_modified=False,model_runs_at_release=0,
                       CPU_runtime=probe.cpu_runtime_state())
    EXECUTION.mkdir()
    write(EXECUTION/"execution_release.json",description)
    print("EXECUTION_RESOURCE_FROZEN selected=5 fixed_denominator=20 old_min_free_MiB=35000 new_min_free_MiB=30000 model_loaded=false",flush=True)
    print("execution_release_sha256="+sha(EXECUTION/"execution_release.json"),flush=True)
    return 0
def stage(policy,manifest,role,gpu,operator,output):
    execution=validate_execution(policy,manifest)
    probe,contract,plan,keyed=verify_environment_and_inputs(policy,False)
    require(plan["settings"]==policy["frozen_settings"],"Inference settings differ")
    import resource_backend
    def factory(which,current_plan):
        # This separately hashed backend contains the unchanged model generation method.
        model=resource_backend.HFBackend(which,current_plan,probe.MODEL,
            probe.ADAPTER if which=="classifier" else None,probe.WEIGHTS,gpu,operator)
        model.identity.update(execution_revision=VERSION,
            actual_backend_source_sha256=manifest["files"]["resource_backend.py"],
            actual_backend_module=str(resource_backend.__file__),
            reference_backend_source_sha256=policy["original_contract_code_sha256"]["route1_pdf_hf_backend_v3.py"],
            contract_code_hashes_describe_original_reference_and_validation_code=True,
            execution_release_sha256=sha(EXECUTION/"execution_release.json"),
            resource_policy=model.resource_budget,
            evidence_source="A100 two-role memory preflight; raw files SHA256 pinned in supplemental execution release")
        return model
    result=contract.run_stage(role,probe.SOURCE,probe.PREPARED,probe.RELEASE,output,
                             contract.source_gate.import_pdf(probe.PDF_DEPS),factory)
    result["execution_revision"]=VERSION
    result["execution_release_sha256"]=sha(EXECUTION/"execution_release.json")
    result["actual_backend_source_sha256"]=manifest["files"]["resource_backend.py"]
    result["code_sha256_describes_original_contract_and_reference_backend"]=True
    # Original artifact hashes remain valid: only run_metadata itself gets extra provenance.
    write(output/"run_metadata.json",result)
    print("FIRST5_STAGE_FINISHED role="+role+" status="+result["status"],flush=True)
    return result["exit_code"]
def run(policy,manifest,gpu,operator,output):
    require(gpu.isdigit() and operator.strip(),"One physical GPU and actual operator required")
    require(not output.exists(),"Output exists; preserve previous attempt")
    release=validate_execution(policy,manifest)
    probe,contract,plan,keyed=verify_environment_and_inputs(policy,False)
    require(plan["settings"]==policy["frozen_settings"],"Inference settings differ")
    output.mkdir()
    write(output/"execution_request.json",{
        **execution_description(policy,manifest),"operator":operator,"gpu":gpu,
        "started_at_utc":now(),"execution_release_sha256":sha(EXECUTION/"execution_release.json"),
        "retry_policy":"none; keep all first attempts","formal_human_acceptance_claimed":False})
    codes={}
    for role in ("classifier","explainer"):
        command=[sys.executable,"-u",str(Path(sys.argv[0]).resolve()),"--stage",role,
                 "--gpu",gpu,"--operator",operator,"--output-dir",str(output/role)]
        env=os.environ.copy()
        env.update(CUDA_VISIBLE_DEVICES=gpu,USE_TORCH="1",USE_TF="0",TOKENIZERS_PARALLELISM="false",
                   PYTHONUNBUFFERED="1",HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1")
        print("FIRST5_STAGE_START role="+role+" points=5",flush=True)
        with (output/(role+".run.log")).open("x",encoding="utf-8") as log:
            completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env)
        codes[role]=completed.returncode
        print("FIRST5_STAGE_END role="+role+" exit_code="+str(completed.returncode),flush=True)
        if completed.returncode:
            write(output/"execution_summary.json",{"status":"FIRST5_EXECUTION_FAILED_NO_AUTO_RETRY",
                "stage_exit_codes":codes,"raw_outputs_retained":True,"finished_at_utc":now(),
                "fixed_denominator":20,"formal_end_to_end_accepted":0})
            return completed.returncode
    # Original assembler keeps all20 rows, selected5 runs and remaining15 not-run.
    stats=contract.assemble(probe.SOURCE,probe.PREPARED,probe.RELEASE,output/"classifier",output/"explainer",
                            output/"assembled",contract.source_gate.import_pdf(probe.PDF_DEPS))
    write(output/"execution_summary.json",{"status":"FIRST5_MODEL_STAGES_FINISHED_HUMAN_REVIEW_PENDING",
        "stage_exit_codes":codes,"assembly":stats,"finished_at_utc":now(),
        "execution_release_sha256":sha(EXECUTION/"execution_release.json"),
        "actual_backend_source_sha256":manifest["files"]["resource_backend.py"],
        "no_unreviewed_reason_for_display":True,"formal_end_to_end_accepted":0})
    print("FIRST5_ASSEMBLED "+json.dumps(stats,ensure_ascii=False),flush=True)
    return 0
def main():
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group()
    modes.add_argument("--verify-only",action="store_true")
    modes.add_argument("--freeze",action="store_true")
    modes.add_argument("--run",action="store_true")
    modes.add_argument("--stage",choices=("classifier","explainer"),help=argparse.SUPPRESS)
    p.add_argument("--gpu");p.add_argument("--operator");p.add_argument("--output-dir",type=Path)
    args=p.parse_args();policy,manifest=package()
    if args.freeze:return freeze(policy,manifest)
    if args.run or args.stage:
        require(args.gpu and args.gpu.isdigit() and args.operator and args.operator.strip() and args.output_dir,
                "Actual operator, one GPU and fresh output-dir required")
        return stage(policy,manifest,args.stage,args.gpu,args.operator,args.output_dir) if args.stage else run(policy,manifest,args.gpu,args.operator,args.output_dir)
    print("PACKAGE_ONLY model_loaded=false GPU_used=false",flush=True)
    return 0
if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as error:
        traceback.print_exc()
        raise SystemExit("FIRST5_EXECUTION_REJECTED "+type(error).__name__+": "+str(error))

