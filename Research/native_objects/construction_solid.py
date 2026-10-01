"""General CSG research builder. No object templates; old experiment stays frozen."""
from copy import deepcopy
import itertools
import math
import numpy as np
import manifold3d as md
from Research.native_objects import construction as prior
from Research.native_objects.experiment import base

M=md.Manifold
SCHEMA=deepcopy(prior.SCHEMA)
F=SCHEMA['properties']['parts']['items']['properties']['forms']['items']
F['properties']['kind']['enum']+=['rounded_box']
for key,value in {'operation':{'type':'string','enum':['add','subtract']},'radius':prior.NUM,
                  'repeat':prior.VEC,'step':prior.VEC}.items():F['properties'][key]=value;F['required'].append(key)
parts=SCHEMA['properties']['parts']['items'];parts['properties']['color']=prior.VEC;parts['required'].append('color')
SCHEMA['properties']['passages']=prior.arr(prior.object_schema({'part':prior.TEXT,'start':prior.VEC,'end':prior.VEC,'radius':prior.NUM,'purpose':prior.TEXT}))
SCHEMA['required'].append('passages')

INSTRUCTIONS=prior.INSTRUCTIONS.replace('1..6 forms each','1..16 forms each').replace(
    'No booleans, hole cutting, arbitrary code, mesh imports, component templates or automatic repairs.',
    'Solid additions and subtractions are supported as described below. No arbitrary code, mesh imports or object templates.').replace(
    'outer must be a part with exactly one box_shell or tube form. Every vertex of inner\nmust fit inside its actual cavity, inset by clearance metres. No containment in solid box/ellipsoid.',
    'outer must enclose inner within its convex envelope, without any solid intersection, at the requested true surface clearance. A solid box cannot contain another solid.')+'''
ADDITIONAL GENERAL OPERATIONS:
Each form has operation add or subtract. All additions union together, then every subtraction is cut
from that union. This affects ONLY this part, never neighboring parts. Through-cuts must extend past
both target surfaces. round_box is NOT a valid spelling: use rounded_box with size giving full outer
extents and radius giving its corner radius (<half the smallest dimension). For other kinds radius=0.
repeat=[nx,ny,nz] contains integer counts 1..16; step=[dx,dy,dz] adds part-local offsets for the copies.
Offset is the FIRST copy, not the array center. A count of [1,1,1] and step=[0,0,0] makes one form.
Maximum 256 expanded forms per object. Use repetition for pattern details instead of verbose copies.
Each part color is RGB [0..1]. Choose restrained, coherent material-like colors for the concept.
Aim for a convincing technical model, not anonymous blocks: use curved silhouettes, readable interfaces,
wall thicknesses, hollow features and visible functional distinctions. Do not add decoration at the
expense of missing major roles. All forms in a single part should form one connected solid.

passages: declare purpose, part ID, start/end points in WORLD coordinates and radius in metres for a
cylindrical free-space probe. The builder tests whether any solid blocks that swept cylinder. Endpoints
must traverse the relevant wall/interface; a probe entirely in air proves nothing. Each important
physical access/opening or flow-through requirement needs a testable passage. Declare them from the
request's purpose, not to pad a list. Keep radius positive. Text purpose is a proposal, not proof.

For mechanisms, explicitly connect the functional chain, not just each part to a housing. Containment
only locates something; it does not mount it or transmit force/motion. Parent is the organizational tree;
additional mount relations can connect parts across branches. Distinguish genuine spatial interfaces
from missing internal engineering. Motion is out of scope, but a part that cannot geometrically reach
its partner is still a construction defect. Avoid unsupported completeness claims.

The application may return independent visual critique and failed geometric checks for one revision.
Address that evidence yourself using the same generic operations. Preserve existing part IDs and role
identity when revising; do not delete a failed constraint or important role just to pass. New parts must
belong to a supplied role group. Do not claim a repair was tested until the builder actually tests it.
'''


def validate(plan,roles):
    if not isinstance(plan,dict) or set(plan)!=set(SCHEMA['required']):raise ValueError('Unexpected solid proposal fields')
    reduced=deepcopy(plan);passages=reduced.pop('passages')
    if not isinstance(passages,list) or len(passages)>32:raise ValueError('Too many passages')
    expanded=0
    for part in reduced['parts']:
        color=part.pop('color')
        if not isinstance(color,list) or len(color)!=3 or any(type(x) not in (float,int) or not math.isfinite(x) or not 0<=x<=1 for x in color):raise ValueError('Invalid color')
        if not isinstance(part['forms'],list) or not 1<=len(part['forms'])<=16:raise ValueError('Invalid solid form count')
        additions=0
        for form in part['forms']:
            op=form.pop('operation');radius=form.pop('radius');repeat=form.pop('repeat');step=form.pop('step')
            if op not in ('add','subtract'):raise ValueError('Invalid operation')
            additions+=op=='add'
            if not isinstance(repeat,list) or len(repeat)!=3 or any(type(n) is not int or not 1<=n<=16 for n in repeat):raise ValueError('Invalid repeat')
            if not isinstance(step,list) or len(step)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>5 for x in step):raise ValueError('Invalid repeat step')
            expanded+=math.prod(repeat)
            if expanded>256:raise ValueError('Expanded operation budget exceeded')
            if type(radius) not in (int,float) or not math.isfinite(radius):raise ValueError('Invalid corner radius')
            if form['kind']=='rounded_box':
                if not 0<radius<min(form['size'])/2:raise ValueError('Corner radius exceeds dimensions')
                form['kind']='box'
            elif radius!=0:raise ValueError('Unused radius must be zero')
        if not additions:raise ValueError('Part has no solid additions')
    # Reuse the frozen contract validator in <=6-form chunks; validate every form
    # without modifying the original input or weakening that experiment's limits.
    check=deepcopy(reduced)
    for p in check['parts']:p['forms']=p['forms'][:6]
    prior.validate(check,roles)
    for p in reduced['parts']:
        for form in p['forms'][6:]:
            check=deepcopy(reduced)
            for q in check['parts']:q['forms']=q['forms'][:1]
            next(q for q in check['parts'] if q['id']==p['id'])['forms']=[form]
            prior.validate(check,roles)
    ids={p['id'] for p in plan['parts']}
    for p in passages:
        if not isinstance(p,dict) or set(p)!={'part','start','end','radius','purpose'} or p['part'] not in ids:raise ValueError('Invalid passage')
        for key in ('start','end'):
            if not isinstance(p[key],list) or len(p[key])!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>10 for x in p[key]):raise ValueError('Invalid passage vector')
        if type(p['radius']) not in (int,float) or not .0001<=p['radius']<=1 or prior.norm(prior.sub(p['start'],p['end']))<.0001:raise ValueError('Invalid passage size')
        if not isinstance(p['purpose'],str) or not 1<=len(p['purpose'])<=400:raise ValueError('Invalid passage purpose')
    return plan


def affine(obj,position,rotation):
    return obj.transform([row+[position[i]] for i,row in enumerate(prior.matrix(rotation))])


def primitive(form,n):
    kind=form['kind'];sx,sy,sz=form['size'];w=form['wall']
    if kind=='box':return M.cube([sx,sy,sz],True)
    if kind=='rounded_box':
        r=form['radius'];ball=M.sphere(r,max(12,n//2))
        return M.batch_hull([ball.translate([x*(sx/2-r),y*(sy/2-r),z*(sz/2-r)]) for x,y,z in itertools.product((-1,1),repeat=3)])
    if kind=='ellipsoid':return M.sphere(1,n).scale([sx/2,sy/2,sz/2])
    if kind in ('cylinder','tube'):
        obj=M.cylinder(sy,1,circular_segments=n,center=True).rotate([-90,0,0]).scale([sx/2,1,sz/2])
        if kind=='tube':obj-=M.cylinder(sy+.002,1,circular_segments=n,center=True).rotate([-90,0,0]).scale([sx/2-w,1,sz/2-w])
        return obj
    if kind=='box_shell':
        return M.cube([sx,sy,sz],True)-M.cube([sx-2*w,sy,sz-2*w],True).translate([0,w,0])
    if kind=='loft':
        v,t=prior.mesh(form,n);t=np.asarray(t,dtype=np.uint32).reshape(-1,3)
        side_count=(len(form['sections'])-1)*n*2
        t[:side_count]=t[:side_count,::-1];t[side_count+n:]=t[side_count+n:,::-1]
        return M(md.Mesh(np.asarray(v,dtype=np.float32),np.ascontiguousarray(t)))
    raise ValueError('Unsupported form')


def solids(plan,roles,resolution=24):
    validate(plan,roles)
    if resolution not in (24,32):raise ValueError('Unsupported resolution')
    result={}
    for p in plan['parts']:
        additions=[];cuts=[]
        for f in p['forms']:
            obj=primitive(f,resolution)
            for xyz in itertools.product(*(range(c) for c in f['repeat'])):
                offset=[f['offset'][i]+xyz[i]*f['step'][i] for i in range(3)]
                (additions if f['operation']=='add' else cuts).append(affine(obj,offset,f['rotation']))
        obj=M.batch_boolean(additions,md.OpType.Add)
        if cuts:obj-=M.batch_boolean(cuts,md.OpType.Add)
        obj=affine(obj,p['position'],p['rotation'])
        if obj.status()!=md.Error.NoError or obj.is_empty() or obj.volume()<=1e-12:raise ValueError('Invalid/empty generated solid: '+p['id'])
        if obj.num_vert()>200000:raise ValueError('Component vertex limit exceeded')
        result[p['id']]=obj
    return result


def probe(start,end,radius):
    direction=np.asarray(end)-np.asarray(start);length=np.linalg.norm(direction);z=direction/length
    helper=np.asarray([1.,0,0]) if abs(z[0])<.8 else np.asarray([0.,1,0])
    x=np.cross(helper,z);x/=np.linalg.norm(x);y=np.cross(z,x)
    transform=np.column_stack((x,y,z,(np.asarray(start)+np.asarray(end))/2))
    return M.cylinder(float(length),radius,circular_segments=24,center=True).transform(transform)


def build(plan,roles,ident,resolution=24):
    objects=solids(plan,roles,resolution)
    pkg=base(ident,{'kind':'application_solid_proposal','resolution':resolution,
         'geometry_library':'manifold3d-3.3.2','limitations':['Proposed design, not verified engineering.']},'metres')
    pkg['origins'].update(geometry='model_generated',semantics='model_generated',hierarchy='model_generated')
    for p in plan['parts']:
        raw=objects[p['id']].to_mesh()
        pkg['parts'].append({'id':p['id'],'semantic_role':p['role'],'parent':p['parent'] or None,
            'subsystem':None,'motion':None,'color':p['color'],'evidence':'model_design_proposal_unverified',
            'vertices':np.asarray(raw.vert_properties)[:,:3].astype(float).tolist(),'triangles':np.asarray(raw.tri_verts).reshape(-1).astype(int).tolist()})
    pkg['declared_capabilities']=['inspect','geometric_explode','reassemble']
    # Reuse actual triangle attachment checks and symmetry; evaluate other relations
    # against the boolean solids rather than assuming an uncut primitive cavity.
    reduced=deepcopy(plan);reduced['containments']=[];reduced['clearances']=[]
    report=prior.relations(reduced,pkg);checks=report['checks']
    def add(kind,relation,passed,measurement):checks.append({'kind':kind,'relation':relation,'passed':bool(passed),'measurement':measurement})
    for p in plan['parts']:
        count=len(objects[p['id']].decompose())
        add('connected_component',{'part':p['id']},count==1,{'solid_islands':count})
    for c in plan['containments']:
        a,b=objects[c['outer']],objects[c['inner']];intersect=(a^b).volume();outside=(b-a.hull()).volume();gap=a.min_gap(b,max(.001,c['clearance']+.001))
        add('containment',c,intersect<=1e-10 and outside<=1e-10 and gap+1e-6>=c['clearance'],
            {'intersection_volume_m3':intersect,'outside_convex_envelope_m3':outside,'minimum_surface_gap_m':gap,'scope':'convex envelope and solid intersection, not semantic containment'})
    for c in plan['clearances']:
        a,b=objects[c['a']],objects[c['b']];gap=a.min_gap(b,max(.001,c['minimum']+.001));overlap=(a^b).volume()
        add('clearance',c,gap+1e-6>=c['minimum'] and overlap<=1e-10,{'gap_m':gap,'intersection_volume_m3':overlap})
    for c in plan['passages']:
        cylinder=probe(c['start'],c['end'],c['radius']);body=objects[c['part']];blocked=(cylinder^body).volume()
        envelope=(cylinder^body.hull()).volume()
        add('passage',c,blocked<=1e-10 and envelope>1e-10,{'blocked_volume_m3':blocked,'convex_envelope_probe_volume_m3':envelope,'scope':'declared finite cylindrical path only'})
    report['declared_relations_passed']=all(c['passed'] for c in checks)
    return pkg,report
