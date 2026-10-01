"""Typed spatial requirement bindings checked over the unchanged geometry executor.

The model proposes the translation; code proves only its declared geometric meaning.
No object recipes, new geometry operations, physics, or semantic-completeness claim.
"""
from copy import deepcopy
import math
import numpy as np
from Research.native_objects import requirement_meaning as meaning
from Research.native_objects import intent_requirements as intent
from Research.native_objects import assembly_connections as geometry

OPERATORS=('on_surface','on_top','radial_outward','outer_end','axis_aligned','parallel_axes')
POLICY={'position_tolerance_m':0.0005,'angle_tolerance_degrees':10.,
        'outer_end_fraction':0.05,'radial_plane_fraction':0.05,'minimum_elongation':1.5,
        'scope':'research visualization tolerances, not manufacturing or physical verification'}
EXTRACT_INSTRUCTIONS=meaning.BOUND_SOURCE_INSTRUCTIONS+'''
SPATIAL TRANSLATION:
Keep spatial intent as predicate other, mode structure, kind relation/constraint, with a short
meaning-preserving value and explicit subject/target IDs. Add a spatial entry with the SAME
requirement id only when a registered operator fully expresses that requirement. Keep unmatched
requirements with no spatial entry; they remain unsupported. Do not weaken the original value.
A composite intent needs separate requirement IDs. No geometry, placements, tolerances or recipes.
Preserve static pose separately from attachment: 'on top of' includes position, not just connection.
Spatial entries contain id, operator, reference, axis; reference/axis must be '' unless specified.
- on_top: subject seated on target's upward-facing surface, measured along the object's +Y.
  A direct face contact is required; this does not verify load capacity.
- on_surface: subject mounted in direct face contact on the target's named exterior side.
  axis is signed +x/-x/+y/-y/+z/-z in the OBJECT frame (+Y up, +Z front). The target
  feature must face that direction and lie at that side's outermost solid extent. Reference=''.
  This supports planar exterior faces; curved/inset/unspecified surfaces remain unsupported.
  Facing forward alone, containment, or an arbitrary internal face cannot prove surface contact.
- radial_outward: >=2 elongated subject members distributed around one target center, their long
  geometric axes pointing radially. axis x/y/z specifies the normal of the radial plane in the
  object's root frame. It does not require equal lengths/radii or perfect angular spacing.
- outer_end: one subject at the outward end of EACH target member, one-to-one. reference names
  the single central entity from which 'outward' is measured. Requires direct geometry-backed mates.
- axis_aligned: one subject axis coincident with each target axis, one-to-one; expressed using real
  cylindrical bore/shaft mate features. This proves static alignment, not mechanical transmission.
- parallel_axes: axes of all subject and target components parallel, not necessarily coincident.
  Subject and target may be the same group. Real cylindrical feature ports are required.
Do not conflate connected with axis_aligned, on_top with arbitrary attachment, or parallel with
coincident. Relative directional phrases beyond this registry remain unsupported. Effects, dynamic
relationships, exact identity and physical verification cannot be authorized by spatial entries.
'''
PLAN_INSTRUCTIONS='''
SPATIAL REQUIREMENT BINDINGS:
spatial_rules are frozen typed translations of specific other/structure requirements. For those
IDs use kind constraint and the following refs, unless honestly unsupported. Do not change any
requirement, rule, reference entity, or operator to repair a failed candidate.
on_surface / on_top / outer_end / axis_aligned: refs ['mate:ID',...]. Cover every subject directly to a target.
outer_end and axis_aligned require an exact one-to-one correspondence covering ALL targets too.
on_top uses face mates at zero separation and upward target / downward subject normals in the
root frame. on_surface uses the signed axis in the rule: target outward and subject opposing
normals, zero face separation, and target contact at its actual outermost extent along that axis.
A driver can extend into an opening, but its mounting face must meet the declared exterior side.
outer_end locates the target-side port on the actual outward geometric extremum
relative to the reference entity center. axis_aligned uses coaxial mates with real bore/shaft ports.
radial_outward: refs ['part:ID',...] for ALL subject parts plus the single target center part.
parallel_axes: refs ['port:ID',...] with exactly one cylindrical axis port for EACH subject/target
part. Subject/target may be the same group; there must be at least two parts.
Ports must already be used by executable mates. A decorative label or unconstrained point is no
proof. The checker measures solved geometry, not placeholder nonroot positions. Part long axes are
measured from the solid mesh; round/isotropic shapes cannot prove radial outward member orientation.
The root frame is the object's coordinate frame; its +Y is up. Normal visualization tolerances
are fixed by the application, not chosen by the model. Geometry checks may reject a fully bound plan.
Spatial admission is not visual or functional approval. Inferred axes/features remain design proposals.
'''


def schema(request,roles):
    out=meaning.bound_source_schema(request,roles);ids=[e['id'] for e in meaning.entity_catalog(roles)]
    ordinary=geometry.base.object_schema({'id':geometry.base.TEXT,
        'operator':{'type':'string','enum':['on_top','axis_aligned','parallel_axes']},
        'reference':{'type':'string','enum':['']},'axis':{'type':'string','enum':['']}})
    radial=deepcopy(ordinary);radial['properties']['operator']['enum']=['radial_outward'];radial['properties']['axis']['enum']=['x','y','z']
    outer=deepcopy(ordinary);outer['properties']['operator']['enum']=['outer_end'];outer['properties']['reference']['enum']=ids
    surface=deepcopy(ordinary);surface['properties']['operator']['enum']=['on_surface'];surface['properties']['axis']['enum']=['+x','-x','+y','-y','+z','-z']
    out['properties']['spatial']=geometry.base.arr({'anyOf':[ordinary,radial,outer,surface]})
    out['required'].append('spatial');return out


def validate(raw,request,roles):
    if not isinstance(raw,dict) or set(raw)!={'requirements','exclusions','spatial'}:raise ValueError('Invalid spatial inventory fields')
    contract=meaning.validate_bound_source_output({k:deepcopy(raw[k]) for k in ('requirements','exclusions')},request,roles)
    contract.update(spatial_rules=deepcopy(raw['spatial']),spatial_rules_sha256=intent.digest(raw['spatial']),
                    spatial_policy_sha256=intent.digest(POLICY))
    rules(contract);return contract


def rules(contract):
    meaning.preflight(contract)
    entries=contract['spatial_rules'];reqs={r['id']:r for r in contract['inventory']['requirements']}
    entities={e['id'] for e in contract['inventory']['entities']};seen=set()
    if intent.digest(entries)!=contract['spatial_rules_sha256'] or intent.digest(POLICY)!=contract['spatial_policy_sha256']:
        raise ValueError('Frozen spatial rules/policy changed')
    if not isinstance(entries,list) or len(entries)>32:raise ValueError('Spatial rule count limit')
    for rule in entries:
        if not isinstance(rule,dict) or set(rule)!={'id','operator','reference','axis'}:raise ValueError('Invalid spatial rule fields')
        rid=rule['id'];r=reqs.get(rid)
        if not r or rid in seen or rule['operator'] not in OPERATORS:raise ValueError('Unknown/duplicate spatial rule')
        seen.add(rid)
        if r['predicate']!='other' or r['mode']!='structure' or r['kind'] not in ('relation','constraint') or r['obligation']=='evidence_required':
            raise ValueError('Spatial adapter cannot authorize a different requirement type')
        if r['subject'] not in entities or r['target'] not in entities:raise ValueError('Spatial endpoints require entity IDs')
        if r['subject']==r['target'] and rule['operator']!='parallel_axes':raise ValueError('Spatial relation needs distinct endpoints')
        if rule['operator']=='outer_end':
            if rule['reference'] not in entities-{r['subject'],r['target']}:raise ValueError('Outer end needs a separate reference entity')
        elif rule['reference']!='':raise ValueError('Unexpected spatial reference')
        if rule['operator']=='radial_outward':
            if rule['axis'] not in ('x','y','z'):raise ValueError('Radial plane axis required')
        elif rule['operator']=='on_surface':
            if rule['axis'] not in ('+x','-x','+y','-y','+z','-z'):raise ValueError('Signed object surface axis required')
        elif rule['axis']!='':raise ValueError('Unexpected spatial axis')
    return {r['id']:r for r in entries}


def preflight(contract):
    registered=rules(contract);out=meaning.preflight(contract)
    out['unsupported']=[r for r in out['unsupported'] if r['id'] not in registered]
    out['blocking']=[r for r in out['unsupported'] if r['obligation'] in ('required','evidence_required')]
    out['planning_allowed']=not out['blocking'];out['pending_spatial_checks']=list(registered)
    out['detail']='Registered spatial checks permit planning only; binding and actual geometry must still pass.'
    return out


def groups(contract,plan):
    return {e['id']:{p['id'] for p in plan['parts'] if p['role']==e['role']} for e in contract['inventory']['entities']}


def binding(rule,requirement,b,plan,group):
    if not isinstance(b,dict) or set(b)!=set(intent.BINDING_SCHEMA['required']):raise ValueError('Invalid spatial binding fields')
    if b['kind']!='constraint' or not isinstance(b['refs'],list) or not b['refs'] or len(b['refs'])>96 or any(not isinstance(x,str) for x in b['refs']) or len(set(b['refs']))!=len(b['refs']):raise ValueError('Spatial constraint needs unique typed references')
    if not isinstance(b['note'],str) or len(b['note'])>400:raise ValueError('Invalid binding note')
    subjects,targets=group[requirement['subject']],group[requirement['target']]
    if not subjects or not targets:raise ValueError('Spatial entity has no components')
    op=rule['operator'];ports={p['id']:p for p in plan['ports']};mates={m['id']:m for m in plan['mates']}
    if op=='radial_outward':
        if len(subjects)<2 or len(targets)!=1 or set(b['refs'])!={'part:'+p for p in subjects|targets}:raise ValueError('Radial binding needs all members and exactly one center')
        return []
    if op=='parallel_axes':
        selected=[ports.get(ref[5:]) if ref.startswith('port:') else None for ref in b['refs']]
        if any(p is None or p['kind'] not in ('outer_axis','bore_axis') for p in selected):raise ValueError('Parallel binding needs cylindrical ports')
        if len(subjects|targets)<2 or len(selected)!=len(subjects|targets) or {p['part'] for p in selected}!=subjects|targets:raise ValueError('Parallel binding must cover every component once')
        return selected
    if op=='outer_end' and len(group[rule['reference']])!=1:raise ValueError('Outer end needs exactly one reference component')
    pairs=[]
    for ref in b['refs']:
        m=mates.get(ref[5:]) if ref.startswith('mate:') else None
        if m is None:raise ValueError('Unknown spatial mate')
        a,z=ports[m['a']],ports[m['b']]
        if a['part'] in targets and z['part'] in subjects:a,z=z,a
        if a['part'] not in subjects or z['part'] not in targets:raise ValueError('Spatial mate endpoints do not match requirement')
        if op in ('on_top','on_surface') and m['kind']!='face' or op=='axis_aligned' and m['kind']!='coaxial':raise ValueError('Wrong mate type for spatial operator')
        pairs.append((a,z,m))
    if len(pairs)!=len(subjects) or {a['part'] for a,z,m in pairs}!=subjects:raise ValueError('Every spatial subject needs exactly one direct target mate')
    if op in ('outer_end','axis_aligned') and (len(pairs)!=len(targets) or {z['part'] for a,z,m in pairs}!=targets):raise ValueError('Spatial relation needs a bijection; target missing or reused')
    return pairs


def coverage(contract,plan,bindings):
    registered=rules(contract);reqs={r['id']:r for r in contract['inventory']['requirements']}
    if not isinstance(bindings,list) or any(not isinstance(b,dict) or b.get('id') not in reqs for b in bindings):raise ValueError('Invalid/unknown requirement binding')
    ids=[b['id'] for b in bindings]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate requirement binding')
    # Delegate only nonspatial IDs; the immutable canonical contract is never modified.
    projected=deepcopy(contract);projected['inventory']['requirements']=[r for r in projected['inventory']['requirements'] if r['id'] not in registered]
    projected['inventory_sha256']=intent.digest(projected['inventory'])
    out=meaning.coverage(projected,plan,[b for b in bindings if b['id'] not in registered])
    table={b['id']:b for b in bindings};group=groups(contract,plan)
    for rid,rule in registered.items():
        b=table.get(rid);r=reqs[rid]
        if b and b.get('kind')=='unsupported':
            if set(b)!=set(intent.BINDING_SCHEMA['required']) or b['refs'] or not isinstance(b['note'],str) or not 1<=len(b['note'])<=400:
                out['errors'].append({'id':rid,'reason':'Unsupported binding needs a reason and no references'})
            else:out['unsupported'].append({'id':rid,'obligation':r['obligation'],'reason':b['note']})
            continue
        try:binding(rule,r,b,plan,group)
        except ValueError as error:out['errors'].append({'id':rid,'reason':str(error)})
        else:out['residual_checks'].append({'id':rid,'check':'Pending measured spatial realization: '+rule['operator']})
    admission=preflight(contract);out['meaning_admission']=admission
    out['blocking_unsupported']=[r for r in out['unsupported'] if r['obligation'] in ('required','evidence_required')]
    out['coverage_complete']=not out['errors'];out['geometry_allowed']=out['coverage_complete'] and not out['blocking_unsupported'] and admission['planning_allowed']
    return out


def _unit(value):
    length=float(np.linalg.norm(value))
    if length<1e-9:raise ValueError('Degenerate spatial direction')
    return value/length


def measurements(contract,plan,bindings,compiled):
    """Read final solids/feature frames. No geometry or pose is edited here."""
    registered=rules(contract);reqs={r['id']:r for r in contract['inventory']['requirements']}
    table={b['id']:b for b in bindings};group=groups(contract,plan);roles=sorted({p['role'] for p in plan['parts']})
    bodies=geometry.solid.solids(compiled,roles)
    vertices={key:np.asarray(body.to_mesh().vert_properties)[:,:3].astype(float) for key,body in bodies.items()}
    centers={key:(v.min(axis=0)+v.max(axis=0))/2 for key,v in vertices.items()}
    parts={p['id']:p for p in compiled['parts']};poses={key:geometry._matrix(p['position'],p['rotation']) for key,p in parts.items()}
    root=next(p for p in compiled['parts'] if not p['parent']);frame=poses[root['id']][:3,:3]
    local=deepcopy(compiled)
    for part in local['parts']:part['position']=[0,0,0];part['rotation']=[0,0,0]
    local_bodies=geometry.solid.solids(local,roles);original={p['id']:p for p in plan['parts']};features={}
    for p in plan['ports']:
        feature=geometry.feature(original[p['part']],p,local_bodies[p['part']])
        features[p['id']]={'frame':poses[p['part']]@feature['frame'],'passed':feature['passed']}
    angle=math.radians(POLICY['angle_tolerance_degrees']);alignment=math.cos(angle);tol=POLICY['position_tolerance_m'];checks=[]
    for rid,rule in registered.items():
        b=table[rid]
        if b['kind']=='unsupported':continue
        r=reqs[rid];op=rule['operator'];measured={};passed=False
        try:
            resolved=binding(rule,r,b,plan,group)
            if op=='radial_outward':
                origin=centers[next(iter(group[r['target']]))];normal=frame[:,'xyz'.index(rule['axis'])]
                basis=frame[:,('xyz'.index(rule['axis'])+1)%3];second=np.cross(normal,basis);bearings=[];heights=[];metrics=[]
                for part in sorted(group[r['subject']]):
                    delta=centers[part]-origin;flat=delta-np.dot(delta,normal)*normal;direction=_unit(flat)
                    verts=vertices[part];_,vectors=np.linalg.eigh(np.cov(verts.T));principal=vectors[:,-1]
                    extents=np.ptp(verts@vectors,axis=0);elongation=float(extents[-1]/max(extents[-2],1e-9))
                    align=float(abs(np.dot(principal,direction)));radius=float(np.linalg.norm(flat));heights.append(float(np.dot(delta,normal)))
                    bearings.append(math.atan2(float(np.dot(flat,second)),float(np.dot(flat,basis))))
                    metrics.append({'part':part,'radius_m':radius,'radial_axis_alignment':align,'elongation':elongation})
                bearings=sorted(bearings);gaps=np.diff(bearings+[bearings[0]+2*math.pi]);radii=[v['radius_m'] for v in metrics]
                plane_spread=max(heights)-min(heights);plane_limit=max(tol,POLICY['radial_plane_fraction']*min(radii))
                passed=all(v['radial_axis_alignment']>=alignment and v['elongation']>=POLICY['minimum_elongation'] for v in metrics) and plane_spread<=plane_limit and min(gaps)>angle and max(gaps)<=math.pi+angle
                measured={'members':metrics,'plane_spread_m':plane_spread,'plane_limit_m':plane_limit,'max_bearing_gap_degrees':math.degrees(float(max(gaps))),'min_bearing_gap_degrees':math.degrees(float(min(gaps)))}
            elif op=='parallel_axes':
                frames=[features[p['id']] for p in resolved];normal=frames[0]['frame'][:3,2]
                alignments=[float(abs(np.dot(normal,f['frame'][:3,2]))) for f in frames]
                passed=all(f['passed'] for f in frames) and min(alignments)>=alignment
                measured={'minimum_axis_alignment':min(alignments),'feature_ports':[p['id'] for p in resolved]}
            else:
                outcomes=[]
                for subject,target,mate in resolved:
                    a,z=features[subject['id']],features[target['id']];fa,fz=a['frame'],z['frame'];ok=a['passed'] and z['passed'];measurement={'subject':subject['part'],'target':target['part'],'mate':mate['id']}
                    if op=='on_surface':
                        direction=frame[:,'xyz'.index(rule['axis'][1])]*(1 if rule['axis'][0]=='+' else -1)
                        outward=float(np.dot(fz[:3,2],direction));opposing=float(np.dot(fa[:3,2],-direction))
                        gap=float(np.linalg.norm(fa[:3,3]-fz[:3,3]))
                        outermost=float(np.max(vertices[target['part']]@direction));actual=float(np.dot(fz[:3,3],direction))
                        extent_error=abs(outermost-actual)
                        ok=ok and outward>=alignment and opposing>=alignment and gap<=tol and extent_error<=tol
                        measurement.update(target_normal_alignment=outward,subject_normal_alignment=opposing,
                            contact_gap_m=gap,surface_extent_error_m=extent_error,object_side=rule['axis'])
                    elif op=='on_top':
                        upward=float(np.dot(fz[:3,2],frame[:,1]));downward=float(np.dot(fa[:3,2],-frame[:,1]));gap=float(np.linalg.norm(fa[:3,3]-fz[:3,3]))
                        ok=ok and upward>=alignment and downward>=alignment and gap<=tol
                        measurement.update(target_up_alignment=upward,subject_down_alignment=downward,contact_gap_m=gap)
                    elif op=='outer_end':
                        origin=centers[next(iter(group[rule['reference']]))];direction=_unit(centers[target['part']]-origin)
                        projections=(vertices[target['part']]-origin)@direction;maximum=float(max(projections));length=float(np.ptp(projections))
                        actual=float(np.dot(fz[:3,3]-origin,direction));error=abs(maximum-actual);limit=max(tol,length*POLICY['outer_end_fraction'])
                        ok=ok and error<=limit
                        measurement.update(end_error_m=error,end_tolerance_m=limit,reference=next(iter(group[rule['reference']])))
                    else:
                        az=fz[:3,2];delta=fa[:3,3]-fz[:3,3];axis_alignment=float(abs(np.dot(fa[:3,2],az)));distance=float(np.linalg.norm(delta-np.dot(delta,az)*az))
                        ok=ok and axis_alignment>=alignment and distance<=tol
                        measurement.update(axis_alignment=axis_alignment,axis_distance_m=distance)
                    outcomes.append({'passed':bool(ok),**measurement})
                passed=all(v['passed'] for v in outcomes);measured={'pairs':outcomes}
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:measured={'error':str(error)}
        checks.append({'kind':'spatial_requirement','requirement_id':rid,'operator':op,'passed':bool(passed),'measurement':measured,
                       'scope':'Measured declared geometry only; semantic feature selection and appearance are unverified.'})
    return checks
