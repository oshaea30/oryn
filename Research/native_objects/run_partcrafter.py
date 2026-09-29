"""Explicit single-run wrapper for a prepared CUDA worker. No provisioning or paid APIs.

Default mode prints a plan. --execute runs a locally installed pinned checkout,
uses already-downloaded pinned model weights offline, and journals before launch.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
from Research.native_objects.prepare_weights import REVISIONS

COMMIT='3d773bf02fad51c7ab31a5615573fec93b287b30'

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()

def plan(repo,image,output,parts,seed):
    if not 1<=parts<=16:raise ValueError('PartCrafter supports 1–16 requested parts')
    return {'id':uuid.uuid4().hex,'baseline':'PartCrafter','revision':COMMIT,
        'input_sha256':digest(image),'num_parts':parts,'seed':seed,
        'supplied':['reference image','part count'],'predicted':['geometry'],
        'not_predicted':['semantic labels','hierarchy','joints','behavior'],
        'manual_repairs':[], 'timeout_seconds':1800,
        'command':[sys.executable,str(Path(__file__).with_name('partcrafter_entry.py')),str(repo),
            '--image_path',str(image),'--num_parts',str(parts),'--seed',str(seed),
            '--num_inference_steps','50','--output_dir',str(output),'--tag','output']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True,type=Path);p.add_argument('--image',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--parts',type=int,default=13);p.add_argument('--seed',type=int,default=0);p.add_argument('--execute',action='store_true')
    a=p.parse_args();repo,image,out=a.repo.resolve(),a.image.resolve(),a.output.resolve()
    if not image.is_file() or image.stat().st_size>20*1024*1024:p.error('Provide a reference image under 20 MiB')
    if out.exists():p.error('Choose a new output directory. Existing runs cannot be overwritten or retried.')
    record=plan(repo,image,out,a.parts,a.seed)
    if not a.execute:print(json.dumps(record,indent=2));return
    rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    if rev!=COMMIT or subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=repo,text=True).strip():p.error('Use the pinned unmodified upstream checkout')
    import torch
    if not torch.cuda.is_available():p.error('This baseline requires an NVIDIA CUDA worker; no CPU substitute')
    # Require an explicit weight manifest; downloads are a separate preparation step.
    weights=repo/'pretrained_weights/oryn-weights.json'
    if not weights.is_file():p.error('Prepare pinned weights and their hash manifest first; see README')
    manifest=json.loads(weights.read_text())
    if set(manifest)!={'revisions','files'} or manifest['revisions']!=REVISIONS or not manifest['files']:p.error('Incomplete weight manifest')
    present={x.relative_to(repo).as_posix() for x in (repo/'pretrained_weights').rglob('*') if x.is_file() and '.cache' not in x.parts and x!=weights}
    if present!=set(manifest['files']):p.error('Unrecorded or missing weight files')
    for name,expected in manifest['files'].items():
        target=(repo/name).resolve()
        if not target.is_relative_to(repo/'pretrained_weights') or digest(target)!=expected:p.error('Weight manifest mismatch')
    record['adapter_sha256']=digest(Path(__file__).with_name('partcrafter_entry.py'))
    record['weights']=manifest
    record['environment']={'python':sys.version,'torch':torch.__version__,'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0)}
    out.mkdir(parents=True,exist_ok=False);journal=out/'run.json';record.update(status='running',started=time.time())
    journal.write_text(json.dumps(record,indent=2));env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    start=time.monotonic();process=None
    try:
        with (out/'inference.log').open('wb') as log:
            process=subprocess.Popen(record['command'],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            code=process.wait(timeout=record['timeout_seconds'])
        if code:raise RuntimeError(f'Inference exited with {code}')
        paths=[out/'output'/f'part_{i:02}.glb' for i in range(a.parts)]
        record['outputs']={x.name:digest(x) for x in paths}
        record['status']='completed'
    except BaseException as e:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        record.update(status='failed',error=type(e).__name__+': '+str(e)[:300])
    finally:
        record['elapsed_seconds']=round(time.monotonic()-start,3);journal.write_text(json.dumps(record,indent=2))
    print(json.dumps({'status':record['status'],'elapsed_seconds':record['elapsed_seconds'],'journal':str(journal)}))
    if record['status']!='completed':sys.exit(1)

if __name__=='__main__':main()
