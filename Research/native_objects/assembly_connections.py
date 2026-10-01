"""Executable, geometry-backed connections over the existing solid research plan.

A narrow rigid placement solver, not a CAD replacement or mechanism simulator.
Face patches and cylindrical bands are verified against the final boolean solid.
No object names, recipes, model calls or model-authored executable code.
"""
from copy import deepcopy
import hashlib
import json
import math
import re
import numpy as np
from Research.native_objects import construction_solid as solid
from Research.native_objects import construction as base

SCHEMA = deepcopy(solid.SCHEMA)
SCHEMA['properties']['ports'] = base.arr(base.object_schema({
    'id': base.TEXT, 'part': base.TEXT, 'kind': {'type':'string','enum':['face','outer_axis','bore_axis']},
    'form': {'type':'integer'}, 'face': {'type':'string','enum':['+x','-x','+y','-y','+z','-z']},
    'span': base.VEC}))
SCHEMA['properties']['mates'] = base.arr(base.object_schema({
    'id': base.TEXT, 'a': base.TEXT, 'b': base.TEXT,
    'kind': {'type':'string','enum':['face','coaxial']},
    'offset': base.NUM, 'twist': base.NUM, 'minimum_clearance': base.NUM, 'minimum_overlap': base.NUM}))
SCHEMA['required'] += ['ports','mates']
# Connections replace point mounts. World-space probes cannot anticipate solved poses.
SCHEMA['properties']['mounts']['maxItems'] = 0
SCHEMA['properties']['passages']['maxItems'] = 0

INSTRUCTIONS = solid.INSTRUCTIONS + '''
EXECUTABLE CONNECTION EXPERIMENT (overrides world placement / point-mount instructions):
Use ports and mates to place every nonroot component. mounts=[] and passages=[].
Only the root's position/rotation is honored. Other poses are initial placeholders;
the executor computes them. Each parent-child pair needs a mate. Every port must be
used by a mate. Keep the same general policy for all requests, with no object recipes.

A port selects a form by zero-based index in its part, never a guessed anchor point.
The selected form must have repeat=[1,1,1]. Its offset and rotation define its frame.
face: select an additive box/rounded_box face (+x/-x/+y/-y/+z/-z), or an additive
solid cylinder cap (+y/-y). span=[0,1] for face. The executor derives the face center,
outward normal and an exposed central circular patch from geometry. It rejects
patches cut away or buried by other geometry. Hollow/tube caps and loft faces are
unsupported. A generic additive mounting feature may supply a real attachment face.
outer_axis: select an additive circular cylinder or tube; face='+y'.
bore_axis: select a subtractive circular cylinder or an additive circular tube;
face='+y'. Axis span=[low,high] selects a nonzero interval in the form's local Y
extent using fractions 0..1. The selected interval must actually have the cylindrical
boundary in the final part. The executor rejects nonexistent holes and buried axes.
Axis direction is form-local +Y; the transverse reference is form-local +X.

A mate references port IDs a and b. face mates align opposite outward normals;
offset is the nonnegative separation in metres (0 means contact), twist is degrees
about port a's normal. Face minimum_clearance=minimum_overlap=0.
coaxial mates require one bore_axis and one outer_axis, align their +Y axes, and
place b's port center offset metres along a's axis. Bore radius must exceed shaft
radius by minimum_clearance and axial overlap must reach minimum_overlap >0.
Neither kind establishes mechanical power transmission, freedom to move or function.
A face port's transverse frame is determined from the face's local coordinate axes.
The executor solves all placements and detects incompatible connection cycles.
All component pairs are checked for positive-volume interference, including mated
pairs. Intentional interpenetrating parts are unsupported in this bounded experiment.

Relations, role identities and logical port bindings are locked before execution.
Repairs may change form dimensions/geometry or port selectors, but must retain all
original parts, roles, parents, ports, mates, clearance/containment/symmetry requirements.
Do not weaken requirements to pass. A deficient requirement set remains a failure of
semantic coverage even if every declared check passes. This is an unverified design.
'''


def _number(x): return type(x) in (int,float) and math.isfinite(x)


def _identifier(x): return isinstance(x,str) and bool(re.fullmatch('[a-z][a-z0-9_]{0,47}',x))


def _matrix(position, rotation):
    out=np.eye(4);out[:3,:3]=base.matrix(rotation);out[:3,3]=position;return out


def _euler(r):
    # Inverse of Rz @ Ry @ Rx, including gimbal lock.
    y=math.asin(float(np.clip(-r[2,0],-1,1)))
    if abs(math.cos(y))>1e-8:x,z=math.atan2(r[2,1],r[2,2]),math.atan2(r[1,0],r[0,0])
    else:x,z=math.atan2(-r[1,2],r[1,1]),0.
    return [math.degrees(v) for v in (x,y,z)]


def _frame(center, normal):
    z=np.array(normal,dtype=float);x=np.array([0.,1.,0.]) if abs(z[0])>.9 else np.array([1.,0.,0.])
    x-=np.dot(x,z)*z;x/=np.linalg.norm(x)
    out=np.eye(4);out[:3,:3]=np.column_stack([x,np.cross(z,x),z]);out[:3,3]=center;return out


def _tube(r0,r1,length):
    outer=solid.M.cylinder(length,r1,circular_segments=24,center=True)
    return outer if r0==0 else outer-solid.M.cylinder(length+.0001,r0,circular_segments=24,center=True)


def _place(shape,frame): return shape.transform(frame[:3,:].tolist())


def _vol_ok(value,probe): return value<=max(1e-20,probe.volume()*1e-5)


def validate(plan,roles):
    if not isinstance(plan,dict) or set(plan)!=set(SCHEMA['required']):raise ValueError('Unexpected connection plan fields')
    ports,mates=plan['ports'],plan['mates']
    if not isinstance(ports,list) or not 0<=len(ports)<=96 or not isinstance(mates,list) or not 0<=len(mates)<=64:raise ValueError('Connection count limit')
    if plan['mounts'] or plan['passages']:raise ValueError('Use executable connections instead of point mounts/world probes')
    ids={p['id'] for p in plan['parts']};bindings={};seen=set()
    for p in ports:
        if not isinstance(p,dict) or set(p)!=set(SCHEMA['properties']['ports']['items']['required']):raise ValueError('Invalid port fields')
        if not _identifier(p['id']) or p['id'] in bindings or p['part'] not in ids:raise ValueError('Invalid/duplicate port ID or part')
        if p['kind'] not in ('face','outer_axis','bore_axis') or p['face'] not in ('+x','-x','+y','-y','+z','-z'):raise ValueError('Invalid port kind/face')
        forms=next(x['forms'] for x in plan['parts'] if x['id']==p['part'])
        if type(p['form']) is not int or not 0<=p['form']<len(forms):raise ValueError('Invalid feature reference')
        if not isinstance(p['span'],list) or len(p['span'])!=2 or not all(_number(x) for x in p['span']) or not 0<=p['span'][0]<p['span'][1]<=1:raise ValueError('Invalid port interval')
        if p['kind']=='face' and p['span']!=[0,1]:raise ValueError('Face interval must be [0,1]')
        if p['kind']!='face' and p['face']!='+y':raise ValueError('Axis reference must use +y')
        bindings[p['id']]=p
    projected={k:deepcopy(v) for k,v in plan.items() if k not in ('ports','mates')}
    for m in mates:
        if not isinstance(m,dict) or set(m)!=set(SCHEMA['properties']['mates']['items']['required']):raise ValueError('Invalid mate fields')
        if not _identifier(m['id']) or m['id'] in seen:raise ValueError('Invalid/duplicate mate ID')
        seen.add(m['id'])
        if m['a'] not in bindings or m['b'] not in bindings or bindings[m['a']]['part']==bindings[m['b']]['part']:raise ValueError('Invalid mate endpoints')
        if m['kind'] not in ('face','coaxial') or any(not _number(m[k]) for k in ('offset','twist','minimum_clearance','minimum_overlap')):raise ValueError('Invalid mate values')
        if abs(m['offset'])>2 or abs(m['twist'])>180 or not 0<=m['minimum_clearance']<=1 or not 0<=m['minimum_overlap']<=5:raise ValueError('Mate range exceeded')
        kinds={bindings[m[k]]['kind'] for k in ('a','b')}
        if m['kind']=='face' and (kinds!={'face'} or m['offset']<0 or m['minimum_clearance']!=0 or m['minimum_overlap']!=0):raise ValueError('Invalid face mate')
        if m['kind']=='coaxial' and (kinds!={'outer_axis','bore_axis'} or m['minimum_overlap']<=0):raise ValueError('Invalid coaxial mate')
        projected['mounts'].append({'a':bindings[m['a']]['part'],'b':bindings[m['b']]['part'],'point_a':[0,0,0],'point_b':[0,0,0]})
    if {x for m in mates for x in (m['a'],m['b'])}!=set(bindings):raise ValueError('Unused ports')
    # Only schema/tree validation uses these dummy anchors; they never count as evidence.
    solid.validate(projected,roles)
    return projected,bindings


def requirements(plan):
    """Stable contract, independent of the candidate's geometry and JSON list order."""
    return {'parts':sorted((p['id'],p['role'],p['parent']) for p in plan['parts']),
            'ports':sorted((p['id'],p['part'],p['kind']) for p in plan['ports']),
            **{k:sorted(deepcopy(plan[k]),key=lambda x:json.dumps(x,sort_keys=True))
               for k in ('mates','containments','clearances','symmetries')}}


def freeze(plan,roles):
    validate(plan,roles)
    return json.dumps(requirements(plan),sort_keys=True,separators=(',',':'))


def check_locked(plan,locked):
    if json.loads(json.dumps(requirements(plan)))!=json.loads(locked):
        raise ValueError('Repair changed locked assembly requirements')


def feature(part,port,body):
    """Resolve a local frame and prove a finite surface region survives booleans."""
    f=part['forms'][port['form']];size=np.array(f['size']);kind=f['kind']
    if f['repeat']!=[1,1,1]:raise ValueError('Repeated form ports need a separate feature')
    transform=_matrix(f['offset'],f['rotation']);axis=port['kind']!='face'
    radius=None;length=None
    if not axis:
        if f['operation']!='add':raise ValueError('Face requires additive feature')
        i='xyz'.index(port['face'][1]);sign=1 if port['face'][0]=='+' else -1
        if kind in ('box','rounded_box'):
            spans=np.delete(size, i)/2-(f['radius'] if kind=='rounded_box' else 0)
            radius=float(min(spans)*.4)
        elif kind=='cylinder' and i==1:
            radius=float(min(size[0],size[2])*.2)
        else:raise ValueError('Unsupported planar feature')
        center=np.zeros(3);center[i]=sign*size[i]/2;normal=np.zeros(3);normal[i]=sign
        frame=transform@_frame(center,normal)
        thickness=min(.00005,radius*.025)
        slab=_tube(0,radius,thickness)
        below=frame.copy();below[:3,3]-=frame[:3,2]*thickness/2
        above=frame.copy();above[:3,3]+=frame[:3,2]*thickness/2
        occupied,empty=_place(slab,below),_place(slab,above)
    else:
        if kind not in ('cylinder','tube') or abs(size[0]-size[2])>1e-9:raise ValueError('Axis requires circular cylinder/tube')
        if port['kind']=='outer_axis' and f['operation']!='add':raise ValueError('Outer axis must be additive')
        if port['kind']=='bore_axis' and not (kind=='cylinder' and f['operation']=='subtract' or kind=='tube' and f['operation']=='add'):raise ValueError('Bore requires tube or cylindrical cut')
        lo,hi=port['span'];length=float((hi-lo)*size[1]);radius=float(size[0]/2-(f['wall'] if port['kind']=='bore_axis' and kind=='tube' else 0))
        if length<.0001 or radius<.0001:raise ValueError('Feature interval too small')
        frame=transform@_frame([0,(lo+hi-1)*size[1]/2,0],[0,1,0])
        thickness=min(.00005,radius*.025,length*.01)
        inner=_place(_tube(radius-thickness,radius,length),frame)
        outer=_place(_tube(radius,radius+thickness,length),frame)
        occupied,empty=(inner,outer) if port['kind']=='outer_axis' else (outer,inner)
        if port['kind']=='bore_axis':
            # A thin annulus alone would accept a blocked bore with an internal plug.
            empty=_place(_tube(0,radius,length),frame)
    missing=(occupied-body).volume();obstructed=(empty^body).volume()
    verified=_vol_ok(missing,occupied) and _vol_ok(obstructed,empty)
    return {'frame':frame,'radius':radius,'length':length,'passed':verified,
            'measurement':{'missing_surface_band_m3':missing,'obstructed_exterior_m3':obstructed,
                           'scope':'finite central face patch' if not axis else 'declared finite cylindrical interval'}}


def _relation(mate):
    matrix=_matrix([0,0,mate['offset']],[0,0,mate['twist']])
    if mate['kind']=='face':matrix=matrix@_matrix([0,0,0],[180,0,0])
    return matrix


def compile_plan(plan,roles,locked):
    projected,ports=validate(plan,roles);check_locked(plan,locked)
    local=deepcopy(projected)
    for p in local['parts']:p['position']=[0,0,0];p['rotation']=[0,0,0]
    bodies=solid.solids(local,roles);parts={p['id']:p for p in projected['parts']}
    features={key:feature(parts[p['part']],p,bodies[p['part']]) for key,p in ports.items()}
    checks=[{'kind':'port_geometry','relation':{'port':key,'part':ports[key]['part']},
             'passed':f['passed'],'measurement':f['measurement']} for key,f in features.items()]
    root=next(p for p in projected['parts'] if not p['parent'])
    poses={root['id']:_matrix(root['position'],root['rotation'])}
    pending=list(plan['mates'])
    while pending:
        progress=False
        for m in pending[:]:
            a,b=ports[m['a']]['part'],ports[m['b']]['part'];fa,fb=features[m['a']]['frame'],features[m['b']]['frame'];relation=_relation(m)
            if a not in poses and b not in poses:continue
            if a not in poses:poses[a]=poses[b]@fb@np.linalg.inv(relation)@np.linalg.inv(fa)
            elif b not in poses:poses[b]=poses[a]@fa@relation@np.linalg.inv(fb)
            pending.remove(m);progress=True
        if not progress:raise ValueError('Disconnected mate graph')
    if set(poses)!=set(parts):raise ValueError('Parts not constrained to root')
    for m in plan['mates']:
        pa,pb=ports[m['a']],ports[m['b']];fa,fb=features[m['a']],features[m['b']]
        actual=poses[pb['part']]@fb['frame'];wanted=poses[pa['part']]@fa['frame']@_relation(m)
        error=float(np.max(np.abs(actual-wanted)));measurement={'frame_max_error':error};passed=error<1e-7
        if m['kind']=='coaxial':
            bore,shaft=(fa,fb) if pa['kind']=='bore_axis' else (fb,fa)
            gap=bore['radius']-shaft['radius'];overlap=max(0,min(fa['length']/2,m['offset']+fb['length']/2)-max(-fa['length']/2,m['offset']-fb['length']/2))
            measurement.update(radial_clearance_m=gap,axial_overlap_m=overlap)
            passed=passed and gap+1e-9>=m['minimum_clearance'] and overlap+1e-9>=m['minimum_overlap']
        checks.append({'kind':'executable_mate','relation':deepcopy(m),'passed':bool(passed),'measurement':measurement})
    for p in projected['parts']:
        p['position']=poses[p['id']][:3,3].tolist();p['rotation']=_euler(poses[p['id']][:3,:3])
        if any(abs(x)>5 for x in p['position']):raise ValueError('Solved position exceeds construction bounds')
    return projected,checks


def build(plan,roles,ident,locked):
    compiled,checks=compile_plan(plan,roles,locked)
    pkg,report=solid.build(compiled,roles,ident)
    report['checks']=[c for c in report['checks'] if c['kind']!='mount']+checks
    bodies=solid.solids(compiled,roles);ids=list(bodies)
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            overlap=(bodies[a]^bodies[b]).volume()
            tolerance=max(1e-20,min(1e-12,min(bodies[a].volume(),bodies[b].volume())*1e-7))
            report['checks'].append({'kind':'assembly_interference','relation':{'a':a,'b':b},
                                     'passed':overlap<=tolerance,'measurement':{'intersection_volume_m3':overlap,'tolerance_m3':tolerance}})
    report['declared_relations_passed']=all(c['passed'] for c in report['checks'])
    report['global_collisions']='all pairs static positive-volume interference checked; no swept motion'
    report['requirement_coverage']='not_assessed; solver cannot prove omitted functional connections'
    report['locked_requirements_sha256']=hashlib.sha256(locked.encode()).hexdigest()
    pkg['source']['connection_solver']='geometry_ports_v1_research'
    return pkg,report,compiled
