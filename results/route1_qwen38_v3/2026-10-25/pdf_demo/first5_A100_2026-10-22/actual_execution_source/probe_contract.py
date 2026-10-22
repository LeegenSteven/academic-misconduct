"""Isolated PDF first5 memory stress probe. Never decode or generate labels."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import threading
import time
import traceback
import zipfile

VERSION='route1_pdf_memory_preflight_v1r2_20261022'
ROOT=Path('/home/admire')
CONTROL=ROOT/'route1_pdf_first5_20261021'
MIGRATED=ROOT/'route1_pdf_cpu_migration_20261021'
SOURCE=MIGRATED/'source'
PREPARED=MIGRATED/'prepared'
RELEASE=ROOT/'route1_pdf_first5_release_20261021/release.json'
MODEL=ROOT/'route1_pdf_model_view_20261021'
PDF_DEPS=ROOT/'route1_pdf_cpu_deps_20261021'
WEIGHTS=ROOT/'citation_integrity_member2/incoming/quality_v1_20261009/cmj_model_weightcheck_20261016/official_sha256sums.txt'
ADAPTER=ROOT/'citation_integrity_member2/incoming/quality_v1_20261009/cmj_sarol_mbio_full_memopt_trial_20261017_gpu2/train/checkpoint-100'
MIB=1024**2

def require(ok,msg):
    if not ok:raise ValueError(msg)
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def verify_package():
    archive=Path(sys.argv[0]).resolve()
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();manifest=json.loads(z.read('manifest.json'))
        require(manifest['version']==VERSION,'Wrong probe package')
        require(len(names)==len(set(names)) and set(names)==set(manifest['files'])|{'manifest.json'},'Unexpected package member')
        for name,expected in manifest['files'].items():
            path=PurePosixPath(name)
            require(not path.is_absolute() and '..' not in path.parts and ':' not in name and '\\' not in name,'Unsafe archive path')
            require(hashlib.sha256(z.read(name)).hexdigest()==expected,'Package file changed: '+name)
        policy=json.loads(z.read('policy.json'))
    print('MEMORY_PROBE_PACKAGE_VERIFIED files='+str(len(manifest['files']))+' model_loaded=false',flush=True)
    return policy

def longest(plan,selected,role):
    require(role in ('classifier','explainer'),'Unknown model role')
    require(len(selected)==len(set(selected))==5,'Exactly first5 points required')
    by_id={r['case_id']:r for r in plan['rows']}
    require(set(selected)<=set(by_id),'Unknown selected point')
    require(all(not by_id[c]['scope_hold'] for c in selected),'Held point in memory probe')
    return max((by_id[c] for c in selected),key=lambda r:r['stages'][role]['input_tokens'])

def allocator_budget(free,total,policy):
    require(free//MIB>=policy['probe_min_free_mib'],'Below probe-only free-memory threshold')
    usable=free-policy['pytorch_headroom_mib']*MIB
    require(0<usable<total,'Invalid shared-GPU allocator budget')
    return usable,usable/total

def cpu_runtime_state():
    # Importing a CPU library is not CUDA initialization. Do not import torch here.
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CPU preflight must hide CUDA devices')
    imported=sys.modules.get('torch')
    initialized=False
    if imported is not None:
        cuda=getattr(imported,'cuda',None)
        require(cuda is not None and callable(getattr(cuda,'is_initialized',None)),
                'Unable to verify CPU-only torch state')
        initialized=bool(cuda.is_initialized())
    require(not initialized,'CPU preflight unexpectedly initialized CUDA')
    return {'torch_imported':imported is not None,'cuda_initialized':initialized,
            'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),
            'model_loaded':False,'GPU_used':False}

def prepare(policy,check_tokenizer):
    if check_tokenizer:
        os.environ.update(CUDA_VISIBLE_DEVICES='',USE_TORCH='0',USE_TF='0',
                          HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    require(sha(CONTROL/'control_manifest.json')==policy['control_manifest_sha256'],'Original first5 controls differ')
    control_manifest=read(CONTROL/'control_manifest.json')
    require(sha(CONTROL/'control.py')==control_manifest['files']['control.py'],'Control code changed')
    spec=importlib.util.spec_from_file_location('original_first5_control',CONTROL/'control.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.verify_control()
    require(sha(RELEASE)==policy['server_release_sha256'],'Different first5 server release')
    sys.path.insert(0,str(MIGRATED/'code/ly'))
    import route1_pdf_pipeline_v3 as contract
    import route1_pdf_hf_backend_v3 as original_backend
    released=read(RELEASE)
    pdf=contract.source_gate.import_pdf(PDF_DEPS)
    items,hashes=contract.load_prepared(SOURCE,PREPARED,pdf)
    plan=contract.validate_release(released,items,hashes)
    selected=released['selected_case_ids']
    require(selected==policy['selected_case_ids'],'Released selected points differ')
    for name,expected in policy['tokenizer_files_sha256'].items():
        require(sha(MODEL/name)==expected,'Model-view tokenizer/config differs: '+name)
    require(sha(MODEL/'generation_config.json')==policy['generation_config_sha256'],'Generation config differs')
    require(sha(MODEL/'model.safetensors.index.json')==policy['weight_index_sha256'],'Model index differs')
    specs={role:longest(plan,selected,role) for role in ('classifier','explainer')}
    keyed={i['case']['case_id']:i for i in items}
    if check_tokenizer:
        os.environ.update(CUDA_VISIBLE_DEVICES='',USE_TORCH='0',USE_TF='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        tokenizer=contract.tokenizer_for(MODEL)
        for role,row in specs.items():
            observed=contract.budget(tokenizer,keyed[row['case_id']][role])
            require(all(observed[k]==row['stages'][role][k] for k in ('input_tokens','input_ids_sha256','within_budget','required_total')),'CPU input token fingerprint differs')
        cpu_runtime_state()
    return contract,original_backend,plan,keyed,specs

def gpu_sample(gpu,pid):
    proc=subprocess.run(['nvidia-smi','-i',gpu,'--query-gpu=uuid,memory.free,memory.used','--format=csv,noheader,nounits'],
                        capture_output=True,text=True,timeout=10)
    require(proc.returncode==0,'GPU inventory failed')
    fields=[x.strip() for x in proc.stdout.strip().split(',')]
    require(len(fields)==3,'Ambiguous GPU inventory')
    apps=subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory,gpu_uuid','--format=csv,noheader,nounits'],
                        capture_output=True,text=True,timeout=10)
    require(apps.returncode==0,'GPU process sampling failed')
    own=None
    for line in apps.stdout.splitlines():
        row=[x.strip() for x in line.split(',')]
        if len(row)==3 and row[0]==str(pid) and row[2]==fields[0]:
            try:own=int(row[1])
            except ValueError:pass
    return {'sampled_at_utc':now(),'gpu_uuid':fields[0],'free_mib':int(fields[1]),'whole_gpu_used_mib':int(fields[2]),'own_process_mib':own}

def worker(policy,role,gpu,output):
    require(not output.exists(),'Worker output exists; preserve old attempt')
    output.mkdir()
    summary={'version':VERSION,'role':role,'status':'running','started_at_utc':now(),'gpu':gpu,
        'model_loaded':False,'base_weights_loaded':False,'model_forward_attempted':False,
        'model_forward_performed':False,'classification_or_explanation_generated':False,
        'formal_points_run':0,'server_release_sha256':policy['server_release_sha256'],
        'frozen_backend_modified':False,'resource_policy':policy['resource_policy'],
        'probe_kind':'prefill plus512 fixed-token cache steps; not actual greedy generation'}
    write(output/'summary.json',summary)
    stop=threading.Event();monitor=None;observations=[];sample_errors=[]
    model=tokenizer=torch=None
    success=False
    try:
        contract,backend,plan,keyed,specs=prepare(policy,False)
        row=specs[role];record=keyed[row['case_id']][role];expected=row['stages'][role]
        summary.update(case_id=row['case_id'],input_sha256=record['input_sha256'],
                       expected_input_tokens=expected['input_tokens'],expected_total_tokens=expected['required_total'],
                       expected_input_ids_sha256=expected['input_ids_sha256'])
        write(output/'input_snapshot.json',record)
        weight_proof=backend.verify_weight_files(MODEL,WEIGHTS)
        if role=='classifier':
            require(sha(ADAPTER/'adapter_model.safetensors')==contract.ADAPTER_SHA,'Mbio adapter weights differ')
            require(sha(ADAPTER/'adapter_config.json')==backend.ADAPTER_CONFIG_SHA,'Mbio adapter config differs')
        # Fresh worker interpreter: never call CPU tokenizer_for() here.
        os.environ.update(CUDA_VISIBLE_DEVICES=gpu,USE_TORCH='1',USE_TF='0',HF_HUB_OFFLINE='1',
                          TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
        import torch
        from transformers import AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig
        require(importlib.metadata.version('transformers')=='5.8.0','Transformers5.8.0 required')
        require(torch.cuda.is_available() and torch.cuda.device_count()==1,'One selected CUDA GPU required')
        free,total=torch.cuda.mem_get_info(0)
        cap,fraction=allocator_budget(free,total,policy['resource_policy'])
        torch.cuda.set_per_process_memory_fraction(fraction,device=0)
        torch.cuda.reset_peak_memory_stats(0)
        summary.update(gpu_used=True,gpu_free_before_load_bytes=free,gpu_total_bytes=total,
                       pytorch_allocator_budget_bytes=cap,pytorch_allocator_fraction=fraction,
                       allocator_cap_limits_pytorch_only_not_all_external_CUDA_allocations=True,
                       versions={n:importlib.metadata.version(n) for n in ('torch','transformers','peft','bitsandbytes','accelerate')})
        def watch():
            with (output/'gpu_samples.jsonl').open('x',encoding='utf-8') as f:
                while not stop.is_set():
                    try:
                        sample=gpu_sample(gpu,os.getpid());observations.append(sample)
                        f.write(json.dumps(sample)+'\n');f.flush()
                    except Exception as error:sample_errors.append(str(error))
                    stop.wait(2)
        monitor=threading.Thread(target=watch,daemon=True);monitor.start()
        tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True,trust_remote_code=False)
        if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
        observed=contract.budget(tokenizer,record)
        require(all(observed[k]==expected[k] for k in ('input_tokens','input_ids_sha256','within_budget','required_total')),'Actual GPU-process token fingerprint differs')
        quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
                                bnb_4bit_compute_dtype=torch.bfloat16,bnb_4bit_use_double_quant=False)
        model=AutoModelForCausalLM.from_pretrained(MODEL,local_files_only=True,trust_remote_code=False,
                                                  quantization_config=quant,device_map={'':0})
        summary['base_weights_loaded']=True
        if role=='classifier':
            from peft import PeftModel
            model=PeftModel.from_pretrained(model,ADAPTER,local_files_only=True)
        model.eval()
        placement=Counter(str(p.device) for p in model.parameters())
        require(placement and all(d.startswith('cuda:') for d in placement),'Unexpected CPU/disk model offload')
        lora=[n for n,m in model.named_modules() if hasattr(m,'lora_A') or hasattr(m,'lora_B')]
        require(bool(lora)==(role=='classifier'),'Actual adapter role differs')
        summary['model_loaded']=True
        identity={'role':role,'base':'Qwen/Qwen3.8-27B','revision':contract.preparation.BASE_REVISION,
            'model_path':str(MODEL),'adapter_loaded':bool(lora),
            'adapter_sha256':contract.ADAPTER_SHA if lora else None,'weights':weight_proof,
            'quantization':quant.to_dict(),'model_class':type(model).__name__,'placement':dict(placement),
            'gpu_loaded':True,'gpu_allocated_after_load_bytes':torch.cuda.memory_allocated(0)}
        write(output/'loaded_model_metadata.json',identity)
        prompt=tokenizer.apply_chat_template([{'role':'system','content':record['system_prompt']},
             {'role':'user','content':record['user_prompt']}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
        encoded=tokenizer(prompt,add_special_tokens=False,truncation=False,return_tensors='pt').to('cuda:0')
        require(encoded['input_ids'].shape[1]==expected['input_tokens'],'Prompt tensor shape differs')
        token_id=tokenizer('0',add_special_tokens=False)['input_ids'][0]
        require(token_id not in tokenizer.all_special_ids,'Stress token must be non-special')
        token=torch.tensor([[token_id]],device='cuda:0',dtype=encoded['input_ids'].dtype)
        mask=encoded['attention_mask'];steps=policy['teacher_forced_steps']
        require(expected['input_tokens']+steps<=plan['settings']['max_length'],'Stress sequence over frozen total budget')
        with torch.inference_mode():
            summary['model_forward_attempted']=True
            outputs=model(**encoded,use_cache=True,logits_to_keep=1,return_dict=True)
            torch.cuda.synchronize(0)
            summary['model_forward_performed']=True
            require(tuple(outputs.logits.shape[:2])==(1,1),'Unexpected prefill last-token logits shape')
            require(outputs.logits.shape[-1]==model.get_output_embeddings().weight.shape[0],'Full vocabulary logits required')
            cache=outputs.past_key_values;require(cache is not None,'KV/recurrent cache missing')
            del outputs
            print('PREFILL_OK role='+role+' input_tokens='+str(expected['input_tokens']),flush=True)
            for i in range(steps):
                mask=torch.cat((mask,torch.ones((1,1),device=mask.device,dtype=mask.dtype)),dim=1)
                outputs=model(input_ids=token,attention_mask=mask,past_key_values=cache,
                              use_cache=True,logits_to_keep=1,return_dict=True)
                cache=outputs.past_key_values
                del outputs
                if (i+1)%64==0:
                    torch.cuda.synchronize(0)
                    print('FIXED_TOKEN_CACHE_STRESS role='+role+' steps='+str(i+1)+'/'+str(steps),flush=True)
        torch.cuda.synchronize(0)
        summary.update(teacher_forced_token_id=token_id,teacher_forced_steps_completed=steps,
                       tokens_selected_from_model_logits=0,text_decoding_calls=0)
        success=True
    except Exception as error:
        summary.update(error_type=type(error).__name__,error=str(error));traceback.print_exc()
    finally:
        if torch is not None:
            try:
                summary.update(pytorch_peak_allocated_bytes=torch.cuda.max_memory_allocated(0),
                               pytorch_peak_reserved_bytes=torch.cuda.max_memory_reserved(0),
                               gpu_free_after_stress_bytes=torch.cuda.mem_get_info(0)[0])
            except Exception as error:summary['cuda_stats_error']=str(error)
        stop.set()
        if monitor:monitor.join(timeout=22)
        own=[r['own_process_mib'] for r in observations if r['own_process_mib'] is not None]
        summary.update(gpu_sampling_count=len(observations),own_process_sample_count=len(own),
                       sampled_process_peak_mib=max(own) if own else None,
                       sampled_gpu_min_free_mib=min((r['free_mib'] for r in observations),default=None),
                       gpu_sampling_errors=sample_errors,finished_at_utc=now())
        if success and not own:
            success=False;summary['error']='NVML own-process memory sampling missing'
        summary['status']='MEMORY_STRESS_PASS_NOT_FORMAL_MODEL_OUTPUT' if success else 'MEMORY_STRESS_FAILED_NO_AUTO_RETRY'
        write(output/'summary.json',summary)
        print('MEMORY_STRESS_RESULT role='+role+' status='+summary['status'],flush=True)
        del model,tokenizer;gc.collect()
    return 0 if success else 1

def supervise(policy,gpu,output):
    require(re.fullmatch(r'\d+',gpu) is not None,'Select exactly one physical GPU index')
    require(not output.exists(),'Output exists; preserve previous run')
    contract,backend,plan,items,specs=prepare(policy,True)
    output.mkdir()
    request={'version':VERSION,'started_at_utc':now(),'package_sha256':sha(Path(sys.argv[0])),
        'gpu':gpu,'release_sha256':sha(RELEASE),'role_order':['classifier','explainer'],
        'longest_input_by_role':{k:v['case_id'] for k,v in specs.items()},'policy':policy,
        'CPU_preflight_runtime':cpu_runtime_state(),
        'formal_points_run':0,'classification_or_explanation_generation':False}
    write(output/'run_request.json',request)
    results=[];code=0
    for role in ('classifier','explainer'):
        print('MEMORY_STRESS_START role='+role+' output='+str(output/role),flush=True)
        command=[sys.executable,'-u',str(Path(sys.argv[0]).resolve()),'--worker',role,'--gpu',gpu,'--output-dir',str(output/role)]
        env=os.environ.copy();env.update(USE_TORCH='1',USE_TF='0',CUDA_VISIBLE_DEVICES=gpu,PYTHONUNBUFFERED='1')
        with (output/(role+'.run.log')).open('x',encoding='utf-8') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env)
        summary=read(output/role/'summary.json') if (output/role/'summary.json').exists() else {'status':'worker_interrupted_no_complete_summary'}
        results.append({'role':role,'exit_code':result.returncode,'result':summary})
        print('MEMORY_STRESS_END role='+role+' status='+summary['status'],flush=True)
        if result.returncode!=0:code=1;break
    write(output/'summary.json',{'version':VERSION,'status':'BOTH_ROLES_MEMORY_STRESS_PASS_NOT_FORMAL_GENERATION' if code==0 and len(results)==2 else 'MEMORY_PREFLIGHT_INCOMPLETE_OR_FAILED',
        'results':results,'formal_points_run':0,'frozen_backend_modified':False,
        'text_generated':False,'model_forwards_performed_in_workers':any(r['result'].get('model_forward_performed',False) for r in results),
        'not_an_exact_greedy_generation_memory_guarantee':True,'finished_at_utc':now()})
    print('MEMORY_PROBE_SUMMARY='+str(output/'summary.json'),flush=True)
    return code

def main():
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group()
    modes.add_argument('--verify-only',action='store_true');modes.add_argument('--preflight',action='store_true')
    modes.add_argument('--run',action='store_true');modes.add_argument('--worker',choices=('classifier','explainer'),help=argparse.SUPPRESS)
    p.add_argument('--gpu');p.add_argument('--output-dir',type=Path)
    a=p.parse_args();policy=verify_package()
    if a.preflight:
        _,_,_,_,specs=prepare(policy,True)
        print('MEMORY_PREFLIGHT_CPU_PASS '+json.dumps({'longest_inputs':{r:{'case_id':x['case_id'],'input_tokens':x['stages'][r]['input_tokens']} for r,x in specs.items()},'runtime':cpu_runtime_state()})+' model_loaded=false GPU_used=false',flush=True)
        return 0
    if a.worker or a.run:
        require(a.gpu and a.output_dir,'GPU index and fresh output-dir required')
        return worker(policy,a.worker,a.gpu,a.output_dir) if a.worker else supervise(policy,a.gpu,a.output_dir)
    print('PACKAGE_ONLY model_loaded=false GPU_used=false formal_points_run=0',flush=True)
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError,TypeError) as error:
        raise SystemExit('MEMORY_PREFLIGHT_REJECTED '+type(error).__name__+': '+str(error))

