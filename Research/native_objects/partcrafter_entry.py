"""Minimal adapter for the pinned PartCrafter pipeline; prepared image input only.

Uses upstream inference parameters directly. No background-removal weights, VLM
part suggestion, style transfer, dummy replacement meshes or mesh repair.
"""
import argparse
import json
from pathlib import Path
import random
import sys

repo=Path(sys.argv.pop(1)).resolve();sys.path.insert(0,str(repo))
import numpy as np
import torch
from PIL import Image
from src.pipelines.pipeline_partcrafter import PartCrafterPipeline

p=argparse.ArgumentParser();p.add_argument('--image_path',required=True);p.add_argument('--num_parts',type=int,required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--num_inference_steps',type=int,required=True);p.add_argument('--output_dir',required=True);p.add_argument('--tag',required=True);a=p.parse_args()
random.seed(a.seed);np.random.seed(a.seed);torch.manual_seed(a.seed);torch.cuda.manual_seed_all(a.seed)
pipe=PartCrafterPipeline.from_pretrained(str(repo/'pretrained_weights/PartCrafter'),local_files_only=True).to('cuda',torch.float16)
with Image.open(a.image_path) as source:
    image=source.convert('RGB')
with torch.inference_mode():
    meshes=pipe(image=[image]*a.num_parts,attention_kwargs={'num_parts':a.num_parts},num_tokens=1024,
        generator=torch.Generator(device=pipe.device).manual_seed(a.seed),num_inference_steps=a.num_inference_steps,
        guidance_scale=7.0,max_num_expanded_coords=1_000_000_000,use_flash_decoder=False).meshes
out=Path(a.output_dir)/a.tag;out.mkdir()
if len(meshes)!=a.num_parts or any(m is None or len(m.faces)==0 for m in meshes):
    raise RuntimeError('Decoder returned a missing or empty part; no replacement geometry')
for i,mesh in enumerate(meshes):mesh.export(out/f'part_{i:02}.glb')
(out/'manifest.json').write_text(json.dumps({'num_parts':a.num_parts,'parts':[f'part_{i:02}.glb' for i in range(a.num_parts)]},indent=2))
