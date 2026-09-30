"""Pinned Cube research worker. Run only on the isolated, bounded rental.

One attempt per stage; unchanged model-produced plans. No production imports,
credentials, manual geometry repair, pruning or inferred animation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import traceback


def save(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');tmp.replace(path)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def download(manifest,weights):
    from huggingface_hub import snapshot_download
    paths={}
    for name,revision in manifest['model_revisions'].items():
        patterns=['*.safetensors','*.json','*.txt','*.model','merges.txt','vocab.json']
        if name=='Qwen/Qwen-Image':patterns=['transformer/config.json']
        paths[name]=snapshot_download(name,revision=revision,local_dir=weights/name,allow_patterns=patterns)
    save(weights/'paths.json',paths)

def stage(args,manifest,case):
    import numpy as np
    import torch
    import trimesh
    from omegaconf import OmegaConf
    sys.path[:0]=[str(args.repo),str(args.repo/'cubepart')]
    paths=json.loads((args.weights/'paths.json').read_text());params=manifest['parameters']
    random.seed(params['seed']);np.random.seed(params['seed']);torch.manual_seed(params['seed']);torch.cuda.manual_seed_all(params['seed'])
    folder=args.output/case['case_id'];folder.mkdir(parents=True,exist_ok=True)
    result_path=folder/(args.stage+'.json')
    if result_path.exists():raise ValueError('Attempt already recorded; no retries.')
    result={'case_id':case['case_id'],'stage':args.stage,'status':'running','started':time.time(),
        'manifest_sha256':sha(args.manifest),'manual_repairs':[]}
    save(result_path,result)
    try:
        if args.stage=='whole':
            from cube3d.inference.engine import Engine
            config=OmegaConf.load(args.repo/'cube3d/configs/open_model_v0.5.yaml')
            config.text_model_pretrained_model_name_or_path=paths['openai/clip-vit-large-patch14']
            cfg=folder/'whole_config.yaml';OmegaConf.save(config,cfg)
            weights=Path(paths['Roblox/cube3d-v0.5'])
            engine=Engine(str(cfg),str(weights/'shape_gpt.safetensors'),str(weights/'shape_tokenizer.safetensors'),device=torch.device('cuda'))
            token_count=len(engine.text_tokenizer(case['whole_shape_prompt'])['input_ids'])
            if token_count>engine.text_tokenizer.model_max_length:raise ValueError('Whole-shape prompt exceeds text encoder; no silent truncation.')
            meshes=engine.t2s([case['whole_shape_prompt']],use_kv_cache=True,resolution_base=params['whole_resolution_base'],top_p=params['whole_top_p'])
            result['text_tokens']=token_count
            roles=['whole_shape']
        else:
            from cube_part.pipelines import PartShapeDenoiserPipeline,ShapeInput
            from cube_part.utils.mesh import load_mesh,sample_surface
            whole=json.loads((folder/'whole.json').read_text())
            if whole['status']!='completed':raise ValueError('Whole stage failed.')
            if sha(folder/'whole_shape.glb')!=whole['meshes'][0]['sha256']:raise ValueError('Whole-shape checksum mismatch.')
            config=OmegaConf.load(args.repo/'cubepart/configs/shape_denoiser_multimesh.yaml')
            config.system.base_model_path=paths['Qwen/Qwen3-VL-4B-Instruct']
            config.system.diffusion_model_type=paths['Qwen/Qwen-Image']
            cfg=folder/'parts_config.yaml';OmegaConf.save(config,cfg)
            weights=Path(paths['Roblox/cubepart'])
            pipe=PartShapeDenoiserPipeline(str(cfg),str(weights/'multi_part_dit.safetensors'),str(weights/'vae.safetensors'),device='cuda',extract_geometry_fn_name='extract_geometry_coarse_to_fine')
            mesh,center,scale=load_mesh(folder/'whole_shape.glb')
            result['input_normalization']={'center':center.tolist(),'scale':float(scale),'rotation_applied':False,'canonical_orientation':'assumed_from_generator_not_verified'}
            surface=sample_surface(mesh,num_samples=params['surface_samples'])
            latent,_=pipe.encode_shape(torch.from_numpy(surface).to(pipe.device).unsqueeze(0).float())
            roles=list(case['part_names'])
            meshes=pipe.input_to_part_shape(ShapeInput(prompt=[list(roles)],latents=latent),
                guidance_scale=params['part_guidance'],resolution_base=params['part_resolution_base'],
                scheduler_type=params['part_scheduler'],timeshift=params['part_timeshift'],
                num_inference_steps=params['part_steps'],seed=params['seed'],output_mesh=True)
        if len(meshes)!=len(roles):raise ValueError('Output count does not match requested roles.')
        result['meshes']=[]
        for index,(role,pair) in enumerate(zip(roles,meshes)):
            vertices,faces=pair
            entry={'index':index,'requested_role':role,'semantic_status':'unverified','status':'missing'}
            result['meshes'].append(entry)
            if vertices is None or faces is None:continue
            vertices=np.asarray(vertices);faces=np.asarray(faces)
            if vertices.ndim!=2 or vertices.shape[1]!=3 or faces.ndim!=2 or faces.shape[1]!=3 or not len(vertices) or not len(faces) or not np.isfinite(vertices).all() or faces.min()<0 or faces.max()>=len(vertices):
                entry['status']='invalid';continue
            mesh=trimesh.Trimesh(vertices,faces,process=False)
            filename='whole_shape.glb' if args.stage=='whole' else f'part_{index:02d}.glb'
            dest=folder/filename;mesh.export(dest)
            entry.update(status='present',file=filename,sha256=sha(dest),vertices=len(vertices),triangles=len(faces),
                         bounds=mesh.bounds.tolist(),watertight=bool(mesh.is_watertight))
        result['status']='completed' if all(m['status']=='present' for m in result['meshes']) else 'missing_or_invalid_geometry'
        result['geometry_quality']='not_assessed'
        result['peak_gpu_bytes']=torch.cuda.max_memory_allocated()
    except Exception:
        result.update(status='failed',error=traceback.format_exc(limit=8))
    result['elapsed_seconds']=time.time()-result['started'];save(result_path,result)
    print(case['case_id'],args.stage,result['status'],flush=True)
    return 0 if result['status']=='completed' else 1

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','repo','weights','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--download',action='store_true');p.add_argument('--stage',choices=['whole','parts']);p.add_argument('--case')
    args=p.parse_args();manifest=json.loads(args.manifest.read_text())
    revision=subprocess.check_output(['git','-C',str(args.repo),'rev-parse','HEAD'],text=True).strip()
    if revision!=manifest['code_revision']:raise ValueError('Wrong source revision.')
    if args.download:
        args.weights.mkdir(parents=True,exist_ok=False);download(manifest,args.weights);return
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    eligible=[c for c in manifest['cases'] if c['status']=='eligible_research_only']
    if args.stage:
        case=next(c for c in eligible if c['case_id']==args.case)
        raise SystemExit(stage(args,manifest,case))
    args.output.mkdir(parents=True,exist_ok=False)
    save(args.output/'manifest.json',manifest)
    env=dict(os.environ);env['PYTHONHASHSEED']=str(manifest['parameters']['seed'])
    for case in eligible:
        for name in ('whole','parts'):
            log=args.output/(case['case_id']+'-'+name+'.log')
            cmd=[sys.executable,__file__,'--manifest',str(args.manifest),'--repo',str(args.repo),'--weights',str(args.weights),'--output',str(args.output),'--stage',name,'--case',case['case_id']]
            try:
                with log.open('x') as stream:r=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT,env=env,timeout=manifest['budget']['max_case_stage_seconds'])
                if r.returncode:break
            except subprocess.TimeoutExpired:
                save(args.output/(case['case_id']+'-'+name+'-timeout.json'),{'status':'timeout','retries':0});break
if __name__=='__main__':main()
