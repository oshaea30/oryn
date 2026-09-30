"""Inspect immutable Cube outputs with the existing research viewer/evaluator."""
import argparse
import json
from pathlib import Path
from Research.native_objects.experiment import base,sha,glb_mesh,write_case,evaluate,inspect_glb


def package(folder,record,ident,allow_oversized):
    p=base(ident,{'kind':'cube_model_output','run':record,'static_preflight':{},
        'allow_oversized_research':allow_oversized},'normalized_source_units')
    p['origins']['geometry']='model_generated'
    # Requested labels are retained as prompts; never promoted to verified semantics.
    for m in record.get('meshes',[]):
        if m['status']!='present':continue
        path=folder/m['file']
        if path.parent.resolve()!=folder.resolve() or sha(path)!=m['sha256']:raise ValueError('Output path/hash mismatch.')
        vertices,triangles=glb_mesh(path,allow_oversized_research=allow_oversized)
        p['source']['static_preflight'][m['file']]=inspect_glb(path.read_bytes())
        p['parts'].append({'id':f"part_{m['index']:02}",'vertices':vertices,'triangles':triangles,
            'color':[0.47,0.59,0.65],'semantic_role':None,'requested_role':m['requested_role'],
            'parent':None,'subsystem':None,'motion':None,'evidence':'model_output_unverified'})
    p['source']['missing_outputs']=[m for m in record.get('meshes',[]) if m['status']!='present']
    p['declared_capabilities']=['inspect','geometric_explode','reassemble']
    return p


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--allow-oversized-research',action='store_true');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);cases=[];failures=[]
    manifest=json.loads((args.run/'manifest.json').read_text())
    for case in manifest['cases']:
        folder=args.run/case['case_id']
        for stage in ('whole','parts'):
            path=folder/(stage+'.json')
            if not path.exists():continue
            record=json.loads(path.read_text());name=case['case_id']+'-'+stage
            if not any(m['status']=='present' for m in record.get('meshes',[])):
                failures.append({'name':name,'status':record['status']});continue
            try:
                p=package(folder,record,name,args.allow_oversized_research)
                write_case(args.output/name,p);cases.append({'name':name,'report':evaluate(p)})
            except ValueError as e:failures.append({'name':name,'error':str(e)})
    (args.output/'index.json').write_text(json.dumps(cases,indent=2))
    (args.output/'failures.json').write_text(json.dumps(failures,indent=2))
    (args.output/'index.html').write_text(Path(__file__).with_name('viewer.html').read_text())
    print(json.dumps({'cases':[c['name'] for c in cases],'failures':failures}))
if __name__=='__main__':main()
