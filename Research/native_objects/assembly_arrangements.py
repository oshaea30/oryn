"""Declared group arrangements measured over the existing connection executor.

An explicit decision is required for repeated entities. It is still the model's
interpretation, not a proof that all essential relationships have been inferred.
"""
from copy import deepcopy
import math
import numpy as np
from Research.native_objects import spatial_requirements as spatial

intent=spatial.intent
geometry=spatial.geometry
POLICY={'position_tolerance_m':0.0005,'angle_tolerance_degrees':10.,'relative_spacing_tolerance':0.05,
        'scope':'declared static feature arrangements; not semantic or engineering certification'}
DIRECTIONS=('+x','-x','+y','-y','+z','-z','parallel','spatial','unsupported')
EXTRACT_INSTRUCTIONS=spatial.EXTRACT_INSTRUCTIONS+'''
ASSEMBLY ARRANGEMENT DECISIONS:
Repeated components need both an explicit group placement and an explicit group orientation
requirement, even when every pairwise connection is already present. Infer the essential static
arrangement from the original request; label inferred requirements honestly. Do not assume that
attachment, radial arms or one-to-one coaxial pairs establish the whole group's orientation.
No object-specific recipe is supplied. Preserve alternative designs and unsupported relationships.

Add assemblies: each entry has id, members (entity IDs), placement and orientation. Each entity
may belong to at most one such group. Cover every entity with a count >1; group singleton entities
only when they share the SAME placement/orientation rule. Give repeated entities an exact count
requirement: inferred when essential to the requested concept, design_choice when incidental.
Keep unrelated groups separate. Do not combine paired groups into one radial pattern: duplicate
bearings at different heights are not one evenly distributed ring.

placement and orientation each reference a DIFFERENT existing other/structure requirement using
field id. Use kind constraint/relation and subject=the member entity for one role, or object for
multiple roles. placement target=reference (or '' for linear/unsupported); orientation target='' except direction spatial retains its original radial target.
Only orientation direction spatial may reuse a spatial ID, as specified below. Keep placement and orientation meaning in their short
requirement values; do not add geometry or coordinates here. Keep the 32-requirement limit.
- placement pattern radial: all member feature centers evenly spaced on one circle around the
  reference entity's center, with a common height. axis x/y/z is the normal of that circle in the
  OBJECT frame. reference must be one separate entity with one instance. Phase and height are free.
- placement pattern linear: all member feature centers in one evenly spaced straight row along
  object axis x/y/z. The row's offset is free. reference=''.
- placement pattern unsupported: retain the true desired relationship; axis=reference=''.
- orientation direction +x/-x/+y/-y/+z/-z: each member's meaningful cylindrical feature axis points
  in that same SIGNED direction of the object frame. In this frame +Y is up, +Z is front. Tilting
  the whole object does not change the declaration. Parallel alone does not establish up or front.
- orientation direction parallel: all meaningful member axes parallel, either sign; do not use this
  to replace an explicitly or necessarily directional arrangement.
- orientation direction spatial: reuse an EXISTING radial_outward spatial requirement as the
  orientation decision for a SINGLE member entity with radial placement. Its subject must be that
  member entity, target the SAME placement reference and axis the SAME radial plane. This preserves
  members pointing in distinct outward directions, measured on their actual elongated geometry.
  Keep that ID only once in requirements and bindings and retain its spatial entry.
- orientation direction unsupported: retain the true meaning when the registry is insufficient.
Every decision must preserve the request. Unsupported never means absent. Do not erase counts or
classify required intent as a design choice to avoid a decision. Do not add animation or simulation.
'''
PLAN_INSTRUCTIONS='''
ASSEMBLY ARRANGEMENT BINDINGS:
assemblies are frozen decisions above pairwise connections. Bind BOTH requirement IDs for each
assembly. Each supported binding is kind constraint, with exactly one existing port:ID for EVERY
part belonging to the assembly's member entities, no duplicate member and no unrelated part.
Use corresponding meaningful features, not arbitrary points. Ports must be used by real mates.
Orientation requires outer_axis or bore_axis ports, selecting the actual main axis of each member.
Placement measures the centers of the selected exposed face/axis features. For radial placement
also include exactly one part:ID for the declared reference entity. Linear placement has no part refs.
Use the same per-member feature ports for placement and a signed/parallel orientation, so both
claims refer to the same geometry. Orientation direction spatial instead reuses its frozen
radial_outward rule and existing part:ID binding; do not replace it with cylinder ports. Its long
member axes are measured by the existing spatial checker. Every repeated entity in the actual plan needs a frozen assembly decision; a missing
one stops before geometry. Do not add another independent repeated entity without a decision.

The object's root frame defines signed x/y/z, not world gravity. Direction +Y is up and +Z is front.
Radial measures equal radii, equal angular gaps and common height around the reference center;
linear measures collinearity and equal spacing along the declared object axis. Each member must be
distinct, with a nonzero radius/spacing. The application fixes tolerances. Satisfy the declarations
through the existing forms, ports and mates; no new geometry operations or guessed nonroot poses.
Unsupported decisions bind kind unsupported, refs=[], with an honest reason. Required unsupported
blocks execution. A repair keeps the same member/requirement IDs and locked port binding refs.
Specific failing members and group requirement IDs are provided; repair geometry without weakening
or deleting the group rule. A passing arrangement does not waive connectivity or interference checks.
'''


def schema(request,roles):
    out=spatial.schema(request,roles);base=geometry.base
    entity_ids=[e['id'] for e in spatial.meaning.entity_catalog(roles)]
    radial=base.object_schema({'id':base.TEXT,'pattern':{'type':'string','enum':['radial']},
        'reference':{'type':'string','enum':entity_ids},'axis':{'type':'string','enum':['x','y','z']}})
    linear=deepcopy(radial);linear['properties']['pattern']['enum']=['linear'];linear['properties']['reference']['enum']=['']
    unsupported=deepcopy(linear);unsupported['properties']['pattern']['enum']=['unsupported'];unsupported['properties']['axis']['enum']=['']
    out['properties']['assemblies']=base.arr(base.object_schema({'id':base.TEXT,
        'members':base.arr({'type':'string','enum':entity_ids}),
        'placement':{'anyOf':[radial,linear,unsupported]},
        'orientation':base.object_schema({'id':base.TEXT,'direction':{'type':'string','enum':list(DIRECTIONS)}})}))
    out['required'].append('assemblies');return out


def validate(raw,request,roles):
    if not isinstance(raw,dict) or set(raw)!={'requirements','exclusions','spatial','assemblies'}:
        raise ValueError('Invalid assembly inventory fields')
    contract=spatial.validate({k:deepcopy(raw[k]) for k in ('requirements','exclusions','spatial')},request,roles)
    contract.update(assemblies=deepcopy(raw['assemblies']),assemblies_sha256=intent.digest(raw['assemblies']),
                    arrangement_policy_sha256=intent.digest(POLICY))
    decisions(contract);return contract


def decisions(contract):
    registered=spatial.rules(contract)
    if intent.digest(contract['assemblies'])!=contract['assemblies_sha256'] or intent.digest(POLICY)!=contract['arrangement_policy_sha256']:
        raise ValueError('Frozen assembly decisions/policy changed')
    reqs={r['id']:r for r in contract['inventory']['requirements']}
    entities={e['id'] for e in contract['inventory']['entities']};counts={};seen=set();assigned=set();result={}
    for r in reqs.values():
        if r['predicate']=='count':
            if r['subject'] in counts:raise ValueError('Each group needs one unambiguous count')
            counts[r['subject']]=int(r['value'])
    entries=contract['assemblies']
    if not isinstance(entries,list) or len(entries)>16:raise ValueError('Assembly count limit')
    for a in entries:
        if not isinstance(a,dict) or set(a)!={'id','members','placement','orientation'}:raise ValueError('Invalid assembly fields')
        if not intent.ident(a['id']) or a['id'] in seen or a['id'] in reqs:raise ValueError('Invalid/duplicate assembly ID')
        seen.add(a['id']);members=a['members']
        if not isinstance(members,list) or not members or any(not isinstance(e,str) for e in members) or len(set(members))!=len(members) or not set(members)<=entities:
            raise ValueError('Invalid assembly members')
        if assigned&set(members):raise ValueError('Member entity assigned to multiple arrangements')
        assigned.update(members)
        if sum(counts.get(e,1) for e in members)<2:raise ValueError('Assembly needs at least two declared members')
        p,o=a['placement'],a['orientation']
        if not isinstance(p,dict) or set(p)!={'id','pattern','reference','axis'} or not isinstance(o,dict) or set(o)!={'id','direction'}:
            raise ValueError('Invalid arrangement decision fields')
        if p['pattern'] not in ('radial','linear','unsupported') or o['direction'] not in DIRECTIONS:raise ValueError('Unknown arrangement operator')
        if p['pattern']=='radial':
            if p['reference'] not in entities-set(members) or counts.get(p['reference'],1)!=1:raise ValueError('Radial arrangement needs one separate center')
        elif p['reference']!='':raise ValueError('Unexpected arrangement reference')
        if p['axis'] not in (('x','y','z') if p['pattern']!='unsupported' else ('',)):raise ValueError('Invalid arrangement axis')
        for kind,rule in (('placement',p),('orientation',o)):
            rid=rule['id'];r=reqs.get(rid)
            linked=kind=='orientation' and rule['direction']=='spatial'
            if not r or rid in result or (rid in registered and not linked):raise ValueError('Unknown/duplicate arrangement requirement')
            if linked:
                existing=registered.get(rid)
                if not existing or existing['operator']!='radial_outward' or len(members)!=1 or p['pattern']!='radial' or existing['axis']!=p['axis']:
                    raise ValueError('Linked orientation requires the matching radial member rule')
            if r['predicate']!='other' or r['mode']!='structure' or r['kind'] not in ('constraint','relation') or r['obligation']=='evidence_required':
                raise ValueError('Arrangement cannot authorize another requirement type')
            if r['subject']!=(members[0] if len(members)==1 else 'object') or r['target']!=(p['reference'] if kind=='placement' or linked else ''):
                raise ValueError('Arrangement requirement endpoints differ from decision')
            result[rid]=(a,kind,rule)
    missing={e for e,n in counts.items() if n>1}-assigned
    if missing:raise ValueError('Repeated entities lack arrangement decisions: '+','.join(sorted(missing)))
    return result


def _unsupported(kind,rule):
    return rule['pattern' if kind=='placement' else 'direction']=='unsupported'


def preflight(contract):
    registered=decisions(contract);out=spatial.preflight(contract)
    supported={rid for rid,(_,kind,rule) in registered.items() if not _unsupported(kind,rule)}
    out['unsupported']=[r for r in out['unsupported'] if r['id'] not in supported]
    out['blocking']=[r for r in out['unsupported'] if r['obligation'] in ('required','evidence_required')]
    out['planning_allowed']=not out['blocking'];out['pending_arrangement_checks']=sorted(supported)
    return out


def _project(contract,ids):
    projected=deepcopy(contract)
    projected['inventory']['requirements']=[r for r in projected['inventory']['requirements'] if r['id'] not in ids]
    projected['inventory_sha256']=intent.digest(projected['inventory']);return projected


def binding(a,kind,rule,b,plan,groups):
    if not isinstance(b,dict) or set(b)!=set(intent.BINDING_SCHEMA['required']):raise ValueError('Missing/invalid arrangement binding')
    if b['kind']!='constraint' or not isinstance(b['refs'],list) or any(not isinstance(x,str) for x in b['refs']) or len(set(b['refs']))!=len(b['refs']) or len(b['refs'])>96:
        raise ValueError('Arrangement needs unique constraint references')
    if not isinstance(b['note'],str) or len(b['note'])>400:raise ValueError('Invalid arrangement binding note')
    expected=set().union(*(groups[e] for e in a['members']))
    if len(expected)<2 or any(not groups[e] for e in a['members']):raise ValueError('Assembly members missing from plan')
    ports={p['id']:p for p in plan['ports']};selected=[];centers=[]
    used={m[k] for m in plan['mates'] for k in ('a','b')}
    for ref in b['refs']:
        if ref.startswith('port:') and ref[5:] in ports:
            p=ports[ref[5:]]
            if p['id'] not in used:raise ValueError('Arrangement feature is not used by a real mate')
            if kind=='orientation' and p['kind'] not in ('outer_axis','bore_axis'):raise ValueError('Orientation needs real cylindrical axes')
            selected.append(p)
        elif ref.startswith('part:'):centers.append(ref[5:])
        else:raise ValueError('Unknown arrangement reference')
    if len(selected)!=len(expected) or {p['part'] for p in selected}!=expected:
        raise ValueError('Arrangement binding must cover every member exactly once')
    if kind=='placement' and rule['pattern']=='radial':
        if len(groups[rule['reference']])!=1 or set(centers)!=groups[rule['reference']] or len(centers)!=1:
            raise ValueError('Radial binding requires its one actual reference component')
    elif centers:raise ValueError('Unexpected arrangement center binding')
    return selected


def binding_lock(contract,bindings):
    ids=decisions(contract)
    return {b['id']:{'kind':b['kind'],'refs':sorted(b['refs'])} for b in bindings if b['id'] in ids}


def coverage(contract,plan,bindings):
    registered=decisions(contract);reqs={r['id']:r for r in contract['inventory']['requirements']}
    if not isinstance(bindings,list) or any(not isinstance(b,dict) or b.get('id') not in reqs for b in bindings):raise ValueError('Invalid arrangement coverage bindings')
    if len({b['id'] for b in bindings})!=len(bindings):raise ValueError('Duplicate requirement binding')
    own_ids=set(registered)-set(spatial.rules(contract))
    out=spatial.coverage(_project(contract,own_ids),plan,[b for b in bindings if b['id'] not in own_ids])
    table={b['id']:b for b in bindings};groups=spatial.groups(contract,plan);resolved={}
    assigned={e for a in contract['assemblies'] for e in a['members']}
    for entity,parts in groups.items():
        if len(parts)>1 and entity not in assigned:out['errors'].append({'id':entity,'reason':'Repeated planned entity lacks a frozen arrangement decision'})
    for rid,(a,kind,rule) in registered.items():
        if rid not in own_ids:continue
        b=table.get(rid);r=reqs[rid]
        if b and b.get('kind')=='unsupported':
            if set(b)!=set(intent.BINDING_SCHEMA['required']) or b['refs'] or not isinstance(b['note'],str) or not 1<=len(b['note'])<=400:
                out['errors'].append({'id':rid,'assembly_id':a['id'],'reason':'Unsupported needs a reason and no references'})
            else:out['unsupported'].append({'id':rid,'obligation':r['obligation'],'reason':b['note']})
            continue
        try:
            if _unsupported(kind,rule):raise ValueError('No registered checker; bind unsupported')
            resolved[rid]=binding(a,kind,rule,b,plan,groups)
        except ValueError as error:out['errors'].append({'id':rid,'assembly_id':a['id'],'reason':str(error)})
        else:out['residual_checks'].append({'id':rid,'check':'Pending measured assembly '+kind})
    for a in contract['assemblies']:
        p,o=a['placement']['id'],a['orientation']['id']
        if p in resolved and o in resolved and {v['id'] for v in resolved[p]}!={v['id'] for v in resolved[o]}:
            out['errors'].append({'id':a['id'],'reason':'Placement and orientation must use the same per-member features'})
    admission=preflight(contract);out['meaning_admission']=admission
    out['blocking_unsupported']=[r for r in out['unsupported'] if r['obligation'] in ('required','evidence_required')]
    out['coverage_complete']=not out['errors'];out['geometry_allowed']=out['coverage_complete'] and not out['blocking_unsupported'] and admission['planning_allowed']
    return out


def _features(plan,compiled):
    parts={p['id']:p for p in compiled['parts']};poses={k:geometry._matrix(p['position'],p['rotation']) for k,p in parts.items()}
    local=deepcopy(compiled)
    for p in local['parts']:p['position']=[0,0,0];p['rotation']=[0,0,0]
    bodies=geometry.solid.solids(local,sorted({p['role'] for p in plan['parts']}));centers={};features={}
    for ident,body in bodies.items():
        bounds=np.array(body.bounding_box());center=(bounds[:3]+bounds[3:])/2
        centers[ident]=(poses[ident]@np.r_[center,1])[:3]
    original={p['id']:p for p in plan['parts']}
    for port in plan['ports']:
        f=geometry.feature(original[port['part']],port,bodies[port['part']])
        features[port['id']]={'frame':poses[port['part']]@f['frame'],'passed':f['passed']}
    root=next(p['id'] for p in compiled['parts'] if not p['parent'])
    return features,centers,poses[root][:3,:3]


def measurements(contract,plan,bindings,compiled):
    registered=decisions(contract);table={b['id']:b for b in bindings};groups=spatial.groups(contract,plan)
    features,centers,frame=_features(plan,compiled);tol=POLICY['position_tolerance_m'];relative=POLICY['relative_spacing_tolerance']
    angle=math.radians(POLICY['angle_tolerance_degrees']);cosine=math.cos(angle);checks=[];linked_checks=None
    for rid,(a,kind,rule) in registered.items():
        if table[rid]['kind']=='unsupported':continue
        if kind=='orientation' and rule['direction']=='spatial':
            if linked_checks is None:linked_checks={v['requirement_id']:v for v in spatial.measurements(contract,plan,bindings,compiled)}
            check=linked_checks[rid]
            checks.append({'kind':'assembly_arrangement','assembly_id':a['id'],'requirement_id':rid,'aspect':kind,
                'passed':check['passed'],'measurement':check['measurement'],'scope':'Reused measured radial member orientation; semantic meaning remains unverified.'})
            continue
        passed=False;metric={}
        try:
            ports=sorted(binding(a,kind,rule,table[rid],plan,groups),key=lambda p:p['part'])
            fs=[features[p['id']] for p in ports];points=np.array([f['frame'][:3,3] for f in fs]);normals=np.array([f['frame'][:3,2] for f in fs])
            valid=all(f['passed'] for f in fs);member_metrics=[]
            if kind=='orientation':
                direction=rule['direction']
                if direction=='parallel':
                    similarities=np.abs(normals@normals.T);alignments=np.min(similarities,axis=1)
                else:
                    axis=frame[:,'xyz'.index(direction[1])]*(1 if direction[0]=='+' else -1);alignments=normals@axis
                for p,value in zip(ports,alignments):member_metrics.append({'part':p['part'],'axis_alignment':float(value),'passed':bool(value>=cosine and features[p['id']]['passed'])})
                passed=valid and all(m['passed'] for m in member_metrics)
                metric={'members':member_metrics,'direction':direction,'minimum_alignment':float(min(alignments))}
            elif rule['pattern']=='radial':
                normal=frame[:,'xyz'.index(rule['axis'])];basis=frame[:,('xyz'.index(rule['axis'])+1)%3];second=np.cross(normal,basis)
                center=centers[next(iter(groups[rule['reference']]))];delta=points-center;heights=delta@normal;flat=delta-np.outer(heights,normal)
                radii=np.linalg.norm(flat,axis=1);radius=float(np.mean(radii));limit=max(tol,radius*relative)
                bearings=np.arctan2(flat@second,flat@basis);order=np.argsort(bearings);sorted_angles=bearings[order]
                gaps=np.diff(np.r_[sorted_angles,sorted_angles[0]+2*math.pi]);ideal=2*math.pi/len(ports)
                angular=np.abs(gaps-ideal);height_error=np.abs(heights-np.mean(heights));radius_error=np.abs(radii-radius)
                for index,p in enumerate(ports):
                    k=int(np.where(order==index)[0][0]);gap_error=max(float(angular[k]),float(angular[(k-1)%len(ports)]))
                    ok=radii[index]>tol and radius_error[index]<=limit and height_error[index]<=limit and gap_error<=angle and fs[index]['passed']
                    member_metrics.append({'part':p['part'],'radius_m':float(radii[index]),'radius_error_m':float(radius_error[index]),
                        'height_error_m':float(height_error[index]),'adjacent_gap_error_degrees':math.degrees(gap_error),'passed':bool(ok)})
                passed=valid and all(m['passed'] for m in member_metrics)
                metric={'members':member_metrics,'radius_m':radius,'distance_tolerance_m':limit,'expected_gap_degrees':360/len(ports)}
            else:
                axis=frame[:,'xyz'.index(rule['axis'])];delta=points-np.mean(points,axis=0);along=delta@axis;off=np.linalg.norm(delta-np.outer(along,axis),axis=1)
                order=np.argsort(along);locations=along[order];pitch=float((locations[-1]-locations[0])/(len(ports)-1));limit=max(tol,pitch*relative)
                targets=np.linspace(locations[0],locations[-1],len(ports));errors=np.abs(locations-targets);gaps=np.diff(locations)
                for index,p in enumerate(ports):
                    k=int(np.where(order==index)[0][0]);ok=off[index]<=limit and errors[k]<=limit and fs[index]['passed']
                    member_metrics.append({'part':p['part'],'line_error_m':float(off[index]),'spacing_error_m':float(errors[k]),'passed':bool(ok)})
                passed=valid and pitch>tol and min(gaps)>tol and all(m['passed'] for m in member_metrics)
                metric={'members':member_metrics,'pitch_m':pitch,'minimum_gap_m':float(min(gaps)),'distance_tolerance_m':limit}
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:metric={'error':str(error)}
        checks.append({'kind':'assembly_arrangement','assembly_id':a['id'],'requirement_id':rid,'aspect':kind,
            'passed':bool(passed),'measurement':metric,'scope':'Solved declared feature geometry; interpretation and feature meaning remain unverified.'})
    return checks
