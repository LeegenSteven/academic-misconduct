"""Bind an existing, verified r2 A100 CPU plan to the user's 13-point confirmation. No model code runs."""
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone
import argparse,hashlib,json,os,sys,zipfile
def require(value,message):
    if not value: raise ValueError(message)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def load_own():
    with zipfile.ZipFile(sys.argv[0]) as z:
        manifest=json.loads(z.read('package_manifest.json'))
        require(z.testzip() is None and set(z.namelist())==set(manifest['files'])|{'package_manifest.json'},'Control package file set/CRC differs')
        for name,h in manifest['files'].items(): require(hashlib.sha256(z.read(name)).hexdigest()==h,'Control package hash differs')
        return json.loads(z.read('approval_record.json')),json.loads(z.read('expected_r2_plan.json'))
def verify_existing(root,bundle,cpu,expected):
    require(sha(bundle)==expected['r2_bundle_sha256'],'Use the approved r2 bundle')
    with zipfile.ZipFile(bundle) as z:
        manifest=json.loads(z.read('package_manifest.json'))
        require(z.testzip() is None and set(z.namelist())==set(manifest['files'])|{'package_manifest.json'},'R2 archive differs')
        for name,h in manifest['files'].items():
            parts=PurePosixPath(name)
            require(not parts.is_absolute() and '..' not in parts.parts,'Unsafe r2 path')
            require(hashlib.sha256(z.read(name)).hexdigest()==h and sha(root/name)==h,'R2 extracted file changed: '+name)
    plan=read(cpu/'runtime_plan.json');migration=read(cpu/'migration_comparison.json')
    require(migration['status']=='REMAINING13_R2_CPU_MIGRATION_PASS' and migration['stage_fingerprints_equal']==40,'R2 CPU migration did not pass')
    require(migration['local_plan_sha256']==expected['local_runtime_plan_sha256'] and migration['actual_plan_sha256']==sha(cpu/'runtime_plan.json'),'CPU comparison report/plan mismatch')
    require(plan['rows']==expected['rows'] and plan['settings']==expected['settings'],'Actual scope/input settings differ')
    require(plan['prepared_files_sha256']==expected['prepared_files_sha256'] and plan['source_files_sha256']==expected['source_files_sha256'] and plan['code_sha256']==expected['code_sha256'],'Code/source/preparation versions differ')
    return plan
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--verify-only',action='store_true');group.add_argument('--freeze',action='store_true')
    parser.add_argument('--root',type=Path);parser.add_argument('--bundle',type=Path);parser.add_argument('--cpu-check-dir',type=Path)
    parser.add_argument('--source-root',type=Path);parser.add_argument('--pymupdf-dir',type=Path);parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args();approval,expected=load_own()
    print('R2_FREEZE_CONTROL_VERIFIED selected=13 fixed_denominator=20 model_loaded=false',flush=True)
    if args.verify_only:return
    require(all([args.root,args.bundle,args.cpu_check_dir,args.source_root,args.pymupdf_dir,args.output_dir]),'Explicit r2/source/CPU paths and new output required')
    require(not args.output_dir.exists(),'Output exists; preserve earlier release')
    root=args.root.resolve();plan=verify_existing(root,args.bundle,args.cpu_check_dir,expected)
    os.environ.update(USE_TORCH='0',USE_TF='0',CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
    sys.path.insert(0,str(root/'code/ly'))
    import route1_pdf_remaining13_runtime_20261024 as adapter
    adapter.install();contract=adapter.base
    prepared=root/'results/route1_qwen38_v3/2026-10-25/pdf_demo/remaining13_preparation_r2_2026-10-24'
    items,hashes=adapter.load_prepared(args.source_root,prepared,adapter.gate.import_pdf(args.pymupdf_dir))
    require(hashes==plan['prepared_files_sha256'],'Runtime artifacts changed')
    require('torch' not in sys.modules,'Freeze unexpectedly imported torch')
    selected=[r['case_id'] for r in expected['selected_scopes']]
    require(len(selected)==len(set(selected))==13,'Wrong selected set')
    chosen={r['case_id']:r for r in expected['selected_scopes']}
    confirmations={'version':adapter.VERSION,'runtime_plan_sha256':sha(args.cpu_check_dir/'runtime_plan.json'),'rows':[]}
    for row in plan['rows']:
        yes=row['case_id'] in chosen
        if yes:require(row['scope_sha256']==chosen[row['case_id']]['scope_sha256'] and not row['scope_hold'],'Scope confirmation/hold mismatch')
        confirmations['rows'].append({'case_id':row['case_id'],'scope_sha256':row['scope_sha256'],'confirmed':yes,
            'reviewer':approval['reviewer'] if yes else None,
            'reviewed_at':approval['acknowledgement_event_at'] if yes else None,
            'reviewed_at_meaning':'Recorded scope acknowledgement event from chat turn metadata; not reading interval' if yes else None,
            'review_source':'Direct user reply '+approval['exact_user_reply']+'; thread='+approval['source_time_proof']['thread_id']+'; user_message='+approval['source_time_proof']['user_message_id']+'; r2_bundle_sha256='+expected['r2_bundle_sha256'] if yes else None,
            'hold_resolution':None,'label':None})
    released=contract.release(plan,confirmations,selected);contract.validate_release(released,items,hashes)
    contract.new_directory(args.output_dir,args.source_root,prepared)
    contract.write_json(args.output_dir/'scope_confirmations.json',confirmations)
    contract.write_json(args.output_dir/'approval_record.json',approval)
    contract.write_json(args.output_dir/'release.json',released)
    receipt={'status':'REMAINING13_R2_FROZEN','created_at_utc':datetime.now(timezone.utc).isoformat(),
        'selected_count':13,'fixed_denominator':20,'release_sha256':sha(args.output_dir/'release.json'),
        'control_bundle_sha256':sha(sys.argv[0]),'A100_runtime_plan_sha256':sha(args.cpu_check_dir/'runtime_plan.json'),
        'A100_CPU_comparison_sha256':sha(args.cpu_check_dir/'migration_comparison.json'),
        'model_loaded':False,'GPU_used':False,'new_labels':0,'new_formal_acceptances':0}
    contract.write_json(args.output_dir/'freeze_receipt.json',receipt)
    print('REMAINING13_R2_FROZEN selected=13 fixed_denominator=20 model_loaded=false GPU_used=false')
    print('release_sha256='+receipt['release_sha256'])
if __name__=='__main__':main()
