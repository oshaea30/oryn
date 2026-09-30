"""Measured research baselines. No model calls, inferred semantics, or mesh repair.

Coordinates: metres, Unity assembly frame for runtime controls; arbitrary source
units for GLB baselines unless a scale has independently been established.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Orchestrator'))
from asset_inspection import inspect_glb
from mesh_islands import decode, components

ORIGINS = {'authored', 'model_generated', 'geometric_decomposition', 'unknown'}
OBJECT_FACETS = ('geometry', 'semantics', 'hierarchy')
FACETS = (*OBJECT_FACETS, 'motion')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def point(p): return [p[k] for k in ('x', 'y', 'z')]
def finite(v,n): return isinstance(v,list) and len(v)==n and all(type(x) in (float,int) and math.isfinite(x) for x in v)
def sub(a,b): return [x-y for x,y in zip(a,b)]
def length(v): return math.sqrt(sum(x*x for x in v))
def bounds(v): return [[min(p[i] for p in v) for i in range(3)], [max(p[i] for p in v) for i in range(3)]]


def rotate(v, axis, angle, pivot):
    p=sub(v,pivot);c,s=math.cos(angle),math.sin(angle)
    dot=sum(a*b for a,b in zip(axis,p))
    cross=[axis[1]*p[2]-axis[2]*p[1],axis[2]*p[0]-axis[0]*p[2],axis[0]*p[1]-axis[1]*p[0]]
    return [pivot[i]+p[i]*c+cross[i]*s+axis[i]*dot*(1-c) for i in range(3)]


def base(ident, source, units):
    return {'schema':'oryn-native-experiment-v1','id':ident,'units':units,'source':source,
            'origins':{f:'unknown' for f in FACETS},'manual_repairs':[],
            'parts':[], 'frames':[], 'declared_capabilities':[],
            'scope':'research_only_not_a_production_object'}


def from_runtime(path):
    raw=json.loads(Path(path).read_text());d=raw['definition']
    package=base(d['Id'],{'kind':'authored_runtime_control','sha256':sha(path)},'metres')
    package['origins']={f:'authored' for f in FACETS}
    links={l['Id']:l for l in d['Links']}
    for p in raw['frames'][0]['parts']:
        l=links[p['id']]
        package['parts'].append({'id':p['id'],'vertices':[point(v) for v in p['vertices']], 'triangles':p['triangles'],
            'color':p['color'],'semantic_role':p['id'].split('_')[0],'parent':l['ParentId'] or None,
            'subsystem':l['Subsystem'],'motion':{'kind':{0:'fixed',1:'rotation'}.get(l['Kind'],'unsupported'),
                'axis':point(l['Axis']),'pivot':point(l['Pivot']),'driver':l['DriverId'] or None,
                'ratio':l['Ratio'],'phase_degrees':l['PhaseDegrees']},'evidence':'authored_unverified'})
    package['frames']=[{'cycle':f['cycle'],'parts':{p['id']:[point(v) for v in p['vertices']] for p in f['parts']}} for f in raw['frames']]
    package['declared_capabilities']=['inspect','explode','reassemble','animate']
    return package


def from_saved_geometry(path):
    # Reuse the existing narrow, lossless decoder. Unsupported GLB layouts fail explicitly.
    data=Path(path).read_bytes();doc,verts,faces=decode(data)
    islands=components(verts,faces)
    package=base('saved-geometry-control',{'kind':'saved_provider_geometry','sha256':sha(path)},'source_units')
    package['origins']['geometry']='geometric_decomposition'
    for i, group in enumerate(islands):
        used=sorted({v for face in group for v in faces[face]});lookup={v:j for j,v in enumerate(used)}
        package['parts'].append({'id':f'island_{i:03}', 'vertices':[list(verts[v]) for v in used],
            'triangles':[lookup[v] for face in group for v in faces[face]],'color':[0.47,0.59,0.65],
            'semantic_role':None,'parent':None,'subsystem':None,'motion':None,'evidence':'unidentified'})
    # Decoder returns node-local coordinates. Preserve source transform explicitly for provenance.
    package['source']['node_transform']={k:doc['nodes'][0][k] for k in ('matrix','translation','rotation','scale') if k in doc['nodes'][0]}
    package['source']['measurement_frame']='source_mesh_local; not a metre-scale or world-space assessment'
    package['declared_capabilities']=['inspect','geometric_explode','reassemble']
    return package


def glb_mesh(path):
    """Read standalone PartCrafter part GLBs for analysis, retaining original files.

    Supports identity mesh nodes beneath identity container nodes, float POSITION,
    triangle primitives with optional indices. Refuses compressed/animated/instanced
    or transformed inputs rather than silently flattening them incorrectly.
    """
    data=Path(path).read_bytes();report=inspect_glb(data)
    if report['preflight']!='PASS': raise ValueError('GLB static preflight failed')
    size=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+size]);binary=data[28+size:]
    if doc.get('animations') or doc.get('skins') or doc.get('extensionsRequired'): raise ValueError('Unsupported animated or compressed GLB')
    nodes=doc.get('nodes',[]);mesh_nodes=[n for n in nodes if 'mesh' in n]
    identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
    if len(mesh_nodes)!=1: raise ValueError('Expected one mesh node per generated part')
    for n in nodes:
        if n.get('matrix',identity)!=identity or n.get('translation',[0,0,0])!=[0,0,0] or n.get('rotation',[0,0,0,1])!=[0,0,0,1] or n.get('scale',[1,1,1])!=[1,1,1]:
            raise ValueError('Non-identity part transform requires an explicit adapter')
    def read(index, count):
        a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
        fmt={5121:'B',5123:'H',5125:'I',5126:'f'}[a['componentType']]
        if a.get('sparse') or a.get('normalized') or v.get('buffer',0)!=0: raise ValueError('Unsupported accessor')
        width=struct.calcsize('<'+fmt*count);start=v.get('byteOffset',0)+a.get('byteOffset',0)
        stride=v.get('byteStride',width)
        return [list(struct.unpack_from('<'+fmt*count,binary,start+i*stride)) for i in range(a['count'])]
    vertices=[];triangles=[]
    for primitive in doc['meshes'][mesh_nodes[0]['mesh']]['primitives']:
        if primitive.get('mode',4)!=4 or primitive.get('targets'): raise ValueError('Expected rigid triangles')
        pos=primitive['attributes']['POSITION'];a=doc['accessors'][pos]
        if a['type']!='VEC3' or a['componentType']!=5126: raise ValueError('Expected float positions')
        points=read(pos,3);offset=len(vertices);vertices.extend(points)
        idx=[i[0] for i in read(primitive['indices'],1)] if 'indices' in primitive else list(range(len(points)))
        if any(type(i)!=int or not 0<=i<len(points) for i in idx): raise ValueError('Invalid index')
        triangles.extend(offset+i for i in idx)
    return vertices,triangles


def from_partcrafter(folder):
    folder=Path(folder).resolve();run=json.loads((folder/'run.json').read_text())
    if run.get('status')!='completed': raise ValueError('A completed recorded inference run is required')
    package=base('partcrafter-'+run['id'],{'kind':'model_output','run':run},'source_units')
    package['origins']['geometry']='model_generated'
    for i in range(run['num_parts']):
        path=folder/'output'/f'part_{i:02}.glb'
        if sha(path)!=run['outputs'][path.name]: raise ValueError('Generated output checksum mismatch')
        vertices,triangles=glb_mesh(path)
        package['parts'].append({'id':f'part_{i:02}','vertices':vertices,'triangles':triangles,'color':[0.47,0.59,0.65],
            'semantic_role':None,'parent':None,'subsystem':None,'motion':None,'evidence':'unidentified'})
    package['source']['supplied_structure']={'part_count':run['num_parts']}
    package['source']['materials']='analysis neutral shading; original GLBs retained without modification'
    package['declared_capabilities']=['inspect','geometric_explode','reassemble']
    return package


def evaluate(p):
    errors=[];checks={};parts=p.get('parts',[]);ids=[part.get('id') for part in parts]
    def check(name,condition,detail):
        checks[name]={'status':'pass' if condition else 'fail','detail':detail}
        if not condition: errors.append(name)
    check('package_version',p.get('schema')=='oryn-native-experiment-v1','Research contract v1')
    check('provenance',all(p.get('origins',{}).get(f) in ORIGINS for f in OBJECT_FACETS) and isinstance(p.get('manual_repairs'),list),'Geometry, semantics and hierarchy identify origin; repairs remain explicit')
    check('unique_components',bool(parts) and len(ids)==len(set(ids)) and all(isinstance(i,str) and i for i in ids),'Exact geometry/component binding')
    invalid=[];tri_count=0
    for part in parts:
        v,t=part.get('vertices',[]),part.get('triangles',[]);tri_count+=len(t)//3
        good=bool(v) and len(t)>=3 and len(t)%3==0 and all(finite(x,3) for x in v) and all(type(i)==int and 0<=i<len(v) for i in t)
        # All-degenerate output includes the upstream dummy-mesh substitution.
        if good:
            nonzero=False
            for j in range(0,len(t),3):
                a,b,c=[v[t[j+k]] for k in range(3)];u,w=sub(b,a),sub(c,a)
                if length([u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0]])>1e-12: nonzero=True;break
            good=nonzero
        if not good: invalid.append(part.get('id'))
    check('usable_geometry',not invalid,'Invalid/empty/all-degenerate components: '+str(invalid))
    def acyclic(field):
        parents={part['id']:(part.get('motion') or {}).get('driver') if field=='driver' else part.get('parent') for part in parts}
        for ident in parents:
            seen=set();cur=ident
            while cur is not None:
                if cur in seen or cur not in parents:return False
                seen.add(cur);cur=parents[cur]
        return True
    check('assembly_references',acyclic('parent'),'Assembly references exist and parent graph is acyclic')
    object_errors=list(errors)
    check('motion_provenance',p.get('origins',{}).get('motion') in ORIGINS,'Motion origin is explicit, including unknown')
    check('motion_references',acyclic('driver'),'Motion drivers exist and driver graph is acyclic')
    motion=[part for part in parts if part.get('motion')]
    valid_motion=all(m['kind'] in ('fixed','rotation') and finite(m.get('axis'),3) and abs(length(m['axis'])-1)<1e-4 and finite(m.get('pivot'),3) and type(m.get('ratio')) in (int,float) and math.isfinite(m['ratio']) and abs(m['ratio'])<=8 and type(m.get('phase_degrees')) in (int,float) and math.isfinite(m['phase_degrees']) for m in [part['motion'] for part in motion])
    if motion:check('motion_parameters',valid_motion,'Bounded fixed/rotation experiment; other mechanisms require another evaluator')
    else:checks['motion_parameters']={'status':'missing','detail':'No predicted or supplied motion'}
    max_error=None
    if p.get('frames') and not errors and len(motion)==len(parts):
        by_id={part['id']:part for part in parts};max_error=0.;frame_errors=[]
        def phase(ident,cycle):
            m=by_id[ident]['motion'];return (phase(m['driver'],cycle) if m.get('driver') else cycle)*m['ratio']+m['phase_degrees']/360
        for frame in p['frames']:
            if not math.isfinite(frame['cycle']) or set(frame['parts'])!=set(ids):frame_errors.append('frame coverage');continue
            for part in parts:
                got=frame['parts'][part['id']];rest=part['vertices'];m=part['motion']
                if len(got)!=len(rest) or not all(finite(v,3) for v in got):frame_errors.append(part['id']);continue
                angle=(phase(part['id'],frame['cycle'])-phase(part['id'],0))*math.tau
                expected=[rotate(v,m['axis'],angle,m['pivot']) for v in rest] if m['kind']=='rotation' else rest
                max_error=max(max_error,max(length(sub(a,b)) for a,b in zip(got,expected)))
        check('runtime_motion_agreement',not frame_errors and max_error<1e-4,f'Sampled actual runtime vertices vs declared motion; max error={max_error}, invalid={frame_errors}')
    else:checks['runtime_motion_agreement']={'status':'not_assessed','detail':'Requires usable joints and independently exported runtime frames'}
    for name,detail in {
        'semantic_correctness':'Part names/count alone cannot establish meaning; independent review required',
        'attachment_fit':'No attachment interfaces/ground truth established; parent graph alone is insufficient',
        'motion_clearance':'No triangle collision sweep implemented; valid axes do not establish clearance',
        'visual_quality':'Requires user review of original materials and geometry in Quest',
        'quest_performance':'No runtime import or frame-time measurement in this experiment',
        'physical_validity':'Kinematic motion is not physical feasibility',
    }.items():checks[name]={'status':'not_assessed','detail':detail}
    # Structural validity is not object completeness or a behavioral judgment.
    # In particular, absent motion must not stand in for a reasoned no-animation decision.
    motion_errors=[name for name in errors if name not in object_errors]
    motion_status=('absent' if not motion and not p.get('frames') and not motion_errors else
                   'failed' if motion_errors else
                   'blocked_by_object' if object_errors else
                   'sampled_agreement' if checks['runtime_motion_agreement']['status']=='pass' else
                   'not_assessed')
    layers={
        'object':{
            'structural_checks_passed':not object_errors,
            'failed_checks':object_errors,
            'missing_output_facets':[f for f in OBJECT_FACETS if p['origins'].get(f)=='unknown'],
            'quality_status':'not_assessed',
            'detail':'Geometry and assembly checks only; semantic meaning, materials, fit and Quest quality need evaluation.'},
        'behavior_decision':{
            'status':'not_assessed',
            'detail':'No application-owned model decision recorded for this object and request. Missing motion does not mean animation is unnecessary.'},
        'motion':{
            'status':motion_status,
            'failed_checks':motion_errors,
            'detail':'Optional motion on this geometry. Sampled agreement does not prove appropriate behavior, clearance or physical validity.'},
    }
    return {'id':p['id'],'origins':p['origins'],'components':len(parts),'triangles':tri_count,
        'structural_checks_passed':not errors,'native_generation_goal_passed':False,
        'manual_repair_count':len(p['manual_repairs']),'checks':checks,'layers':layers,
        'missing_output_facets':[f for f in FACETS if p['origins'][f]=='unknown'],
        'verdict':'Control/evidence only; complete native generation is not demonstrated.'}


def write_case(folder,p):
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'package.json').write_text(json.dumps(p,allow_nan=False,separators=(',',':')))
    (folder/'report.json').write_text(json.dumps(evaluate(p),allow_nan=False,indent=2))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path);parser.add_argument('--saved-glb',type=Path);parser.add_argument('--partcrafter',type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if args.output.exists():parser.error('Output already exists; use a new run folder')
    cases=[]
    if args.runtime:cases.append(('authored-control',from_runtime(args.runtime)))
    if args.saved_glb:cases.append(('saved-geometry-control',from_saved_geometry(args.saved_glb)))
    if args.partcrafter:cases.append(('partcrafter',from_partcrafter(args.partcrafter)))
    if not cases:parser.error('At least one input is required')
    args.output.mkdir(parents=True)
    for name,p in cases:write_case(args.output/name,p)
    (args.output/'index.json').write_text(json.dumps([{'name':n,'report':evaluate(p)} for n,p in cases],indent=2))
    (args.output/'index.html').write_text((Path(__file__).with_name('viewer.html')).read_text())
    print(json.dumps([{'name':n,'components':len(p['parts']),'structural_checks_passed':evaluate(p)['structural_checks_passed']} for n,p in cases]))

if __name__=='__main__':main()
