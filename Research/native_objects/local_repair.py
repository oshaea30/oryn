"""Model-authored geometry edits within a measured, deterministic repair scope.

No object recipes. No edited constraints, replacement assemblies or relaxed checks.
Shared shape consumers are dependencies; placements are still solved and checked globally.
"""
from copy import deepcopy
from Research.native_objects import compact_construction as compact
from Research.native_objects import repair_feedback as feedback

base=compact.base
INSTRUCTIONS='''
BOUNDED LOCAL REPAIR (overrides full construction output syntax):
Return only the patch schema. base_sha256 must match the supplied original compact plan.
shapes contains replacements for EXISTING allowed shape IDs, each with its full corrected forms.
ports contains replacements for EXISTING allowed port IDs. Preserve port id/part/kind; only
form, face and span may change. Omit unchanged entries. Never add/delete parts, shapes, ports,
requirements, mates, groups, bindings or constraints. Original untouched data is retained exactly.
Shared shapes affect every listed consumer; all consumers must be in the application-computed scope.
Shapes, port selectors and their actual geometry may change; coordinate fixes must be expressed
through the existing geometry/mates. The application solves dependent poses and validates the ENTIRE
assembly, including all-pair interference and global arrangements. Preserve every previously true
fact in application_feedback.preserve. Correct only measured failures in allowed_parts.
If those failures cannot be repaired within this scope, return status unsupported, no changes,
and a brief reason. Do not guess a different requirement or revise unrelated components.
Use status patch for nonempty edits and reason=''. A patch is a proposal, never a passing verdict.
'''


def scope(raw,report):
    parts={p['id']:p for p in raw['parts']};ports={p['id']:p for p in raw['ports']};allowed=set();unresolved=[]
    for check in report['checks']:
        if check['passed']:continue
        before=set(allowed);rel=check.get('relation',{})
        for key in ('a','b','part','inner','outer'):
            value=rel.get(key)
            if value in parts:allowed.add(value)
            elif value in ports:allowed.add(ports[value]['part'])
        if rel.get('port') in ports:allowed.add(ports[rel['port']]['part'])
        measurement=check.get('measurement',{})
        for m in measurement.get('members',[]):
            if m.get('passed') is False and m.get('part') in parts:allowed.add(m['part'])
        for pair in measurement.get('pairs',[]):
            if pair.get('passed') is False:
                allowed.update(pair[k] for k in ('subject','target') if pair.get(k) in parts)
        if before==allowed and not any(v in allowed for v in rel.values() if isinstance(v,str)):
            # Some failures overlap earlier ones; no broad fallback that unlocks the object.
            if not measurement.get('members') and not measurement.get('pairs'):unresolved.append(check['kind'])
    direct=sorted(allowed);shapes={p['shape'] for p in parts.values() if p['id'] in allowed}
    allowed.update(p['id'] for p in parts.values() if p['shape'] in shapes)
    value={'base_sha256':feedback.digest(raw),'direct_parts':direct,'allowed_parts':sorted(allowed),
        'allowed_shapes':sorted(shapes),'allowed_ports':sorted(p['id'] for p in ports.values() if p['part'] in allowed),
        'unresolved_failures':unresolved,'dependency_rule':'shared shape consumers; solved poses and all constraints revalidated globally'}
    return {**value,'scope_sha256':feedback.digest(value)}


def verify(raw,s):
    value={k:v for k,v in s.items() if k!='scope_sha256'}
    if feedback.digest(value)!=s['scope_sha256'] or feedback.digest(raw)!=s['base_sha256']:raise ValueError('Stale or changed repair scope')


def schema(raw,s):
    verify(raw,s)
    shape=deepcopy(compact.SCHEMA['properties']['shapes']['items']);shape['properties']['id']={'type':'string','enum':s['allowed_shapes'] or ['no_allowed_shape']}
    port=deepcopy(compact.SCHEMA['properties']['ports']['items']);port['properties']['id']={'type':'string','enum':s['allowed_ports'] or ['no_allowed_port']}
    return base.object_schema({'base_sha256':{'type':'string','enum':[s['base_sha256']]},
        'status':{'type':'string','enum':['patch','unsupported']},'reason':base.TEXT,
        'shapes':base.arr(shape),'ports':base.arr(port)})


def apply(raw,patch,s,contract):
    verify(raw,s)
    if not isinstance(patch,dict) or set(patch)!={'base_sha256','status','reason','shapes','ports'} or patch['base_sha256']!=s['base_sha256']:raise ValueError('Invalid/stale repair patch')
    if patch['status'] not in ('patch','unsupported') or not isinstance(patch['reason'],str) or len(patch['reason'])>400:raise ValueError('Invalid repair result')
    if patch['status']=='unsupported':
        if patch['shapes'] or patch['ports'] or not patch['reason']:raise ValueError('Unsupported repair requires reason and no edits')
        return None,{'status':'unsupported','reason':patch['reason']}
    if patch['reason'] or not patch['shapes'] and not patch['ports']:raise ValueError('Patch requires nonempty edits')
    out=deepcopy(raw);changed={}
    for name in ('shapes','ports'):
        edits=patch[name]
        if not isinstance(edits,list) or len(edits)>len(s['allowed_'+name]):raise ValueError('Repair edit count exceeds scope')
        table={v['id']:i for i,v in enumerate(raw[name])};seen=set()
        for edit in edits:
            if not isinstance(edit,dict) or edit.get('id') not in s['allowed_'+name] or edit['id'] in seen:raise ValueError('Repair targets an unrelated or duplicate ID')
            seen.add(edit['id']);old=raw[name][table[edit['id']]]
            if set(edit)!=set(old):raise ValueError('Repair changed record fields')
            if name=='ports' and any(old[k]!=edit[k] for k in ('id','part','kind')):raise ValueError('Repair changed logical port binding')
            if old==edit:raise ValueError('Repair includes an unchanged record')
            out[name][table[edit['id']]]=deepcopy(edit)
        changed[name]=sorted(seen)
    before=compact.expand(raw,contract);after=compact.expand(out,contract)
    compact.assembly.check_locked(after,compact.assembly.freeze(before,sorted({p['role'] for p in before['parts']})))
    protected=[p['id'] for p in raw['parts'] if p['id'] not in s['allowed_parts']]
    old={p['id']:p for p in before['parts']};new={p['id']:p for p in after['parts']}
    if any(old[k]!=new[k] for k in protected):raise ValueError('Unrelated component changed')
    return out,{'status':'proposed','changed':changed,'protected_parts':protected,
        'protected_geometry_unchanged':True,'base_sha256':s['base_sha256'],'result_sha256':feedback.digest(out),
        'validation_scope':'full assembly; patch admission alone is not success'}
