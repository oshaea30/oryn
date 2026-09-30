"""Offline, lossless planning-to-Cube capability check. Not a production generator."""
import argparse
import hashlib
import json
from pathlib import Path

REVISION='3c6d06ddbef3160a1e1950cb13ab63dd12a61e50'
MAX_PARTS=8  # Pinned PartShapeDenoiserPipeline.input_to_part_shape allocates eight slots.
MODELS={
 'Roblox/cube3d-v0.5':'8cab4886803e8210f4282aef212c6b6b92f68d16',
 'Roblox/cubepart':'28431d124e77040fcaf34c0a71623ff61d35a6c0',
 'Qwen/Qwen3-VL-4B-Instruct':'ebb281ec70b05090aa6165b016eac8ec08e71b17',
 'openai/clip-vit-large-patch14':'32bd64288804d66eefd0ccbe215aa642df71cc41',
 'Qwen/Qwen-Image':'75e0b4be04f60ec59a75f475837eced720f823b6',
}
def digest_bytes(data):return hashlib.sha256(data).hexdigest()
def prepare(record,source_hash):
    cases=[]
    for item in record['items']:
        candidate=item['candidate'];plan=candidate['plan']
        names=[c['name'] for c in plan['components']]
        if plan['fidelity'] not in ('generic_design','creative_concept') or plan['next_step']!='propose_geometry' or plan['retrieval']!='none':
            status,reason='blocked_evidence','Plan does not propose a generic/creative geometry test.'
        elif not 1<=len(names)<=MAX_PARTS:
            status,reason='unsupported_part_count','Pinned CubePart supports one to eight named groups; no merging or truncation permitted.'
        else:
            status,reason='eligible_research_only','Names are unchanged planned groups, not verified mesh identities or individual instances.'
        cases.append({'case_id':item['case_id'],'request':item['request'],'plan':plan,
            'status':status,'reason':reason,'whole_shape_prompt':plan['object'],'part_names':names,
            'production_generation_allowed':False})
    return {'id':'cube-bridge-001','source_plan_sha256':source_hash,'code_revision':REVISION,
        'model_revisions':MODELS,'cases':cases,'max_parts':MAX_PARTS,
        'parameters':{'seed':0,'whole_resolution_base':8.0,'whole_top_p':None,
            'whole_engine':'Engine','part_resolution_base':8.5,'part_steps':50,
            'part_guidance':7.5,'part_timeshift':4.0,'part_scheduler':'dpm_solver','surface_samples':128000},
        'budget':{'max_rentals':1,'max_hours':2,'max_gpu_usd_hour':1.59,'container_gb':100,
                  'max_estimated_usd':3.50,'max_case_stage_seconds':1200},
        'policy':{'retries':0,'manual_repairs':0,'merge_or_drop_roles':False,'seed_search':False,
                  'license_scope':'research_only','native_generation_goal_passed':False}}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plans',type=Path,default=Path(__file__).parent/'results/planning-001.json')
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    raw=args.plans.read_bytes();manifest=prepare(json.loads(raw),digest_bytes(raw))
    with args.output.open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
    print(json.dumps({c['case_id']:c['status'] for c in manifest['cases']}))
if __name__=='__main__':main()
