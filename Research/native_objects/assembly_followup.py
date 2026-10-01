"""Assembly 011: compact intent, named exterior contact, measured repair preservation."""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
from Research.native_objects import arrangement_experiment as previous
from Research.native_objects import compact_requirements as codec
from Research.native_objects import repair_feedback as repair

prior=previous.prior
pipeline=previous.pipeline
transport=previous.transport
arrangements=previous.arrangements
SOURCE=previous.SOURCE
ROOT=previous.ROOT
SPECS=previous.SPECS
CASES=previous.CASES
REPLAY_CASE='cooling-fan-row'
BASELINE=SOURCE/'results/assembly-010'
OPERATIONS=tuple(c+'/'+s+'/'+str(a) for c in CASES if c!=REPLAY_CASE for s,count in [('extract',1),('plan',2)] for a in range(count))+(REPLAY_CASE+'/plan/1',)
BATCH=transport.Batch('assembly-011',OPERATIONS,950_000_000,4_000_000_000,5_000_000_000)


def selected(stage):
    p=previous.selected(stage);p['profile']='assembly_followup_'+stage;return p


def body_for(stage,context):
    p=selected(stage)
    if stage=='extract':
        request=context['original_request'];roles=context['proposed_role_groups']
        content={'request':request,'entities':arrangements.spatial.meaning.entity_catalog(roles),
            'source_units':arrangements.spatial.meaning.source_units(request)}
        schema=codec.schema(request,roles);instructions=arrangements.EXTRACT_INSTRUCTIONS+codec.INSTRUCTIONS
    else:
        content=pipeline.compact.planner_context(context);schema=pipeline.compact.SCHEMA
        instructions=pipeline.compact.INSTRUCTIONS+arrangements.spatial.PLAN_INSTRUCTIONS+arrangements.PLAN_INSTRUCTIONS+repair.INSTRUCTIONS+pipeline.compact.PLANNER_CONTEXT_INSTRUCTIONS
    return p,prior.body(p,instructions,json.dumps(content),schema,'oryn_assembly_followup_'+stage)


def request(case,stage,attempt,context,folder,ledger,key):
    op=case+'/'+stage+'/'+str(attempt)
    if op not in BATCH.cases:raise prior.CommandError('Outside frozen assembly follow-up')
    p,body=body_for(stage,context)
    raw,bill=transport.dispatch(BATCH.operation_id(op),p,body,folder,ledger,key,batch=BATCH,timeout=240 if stage=='plan' else 120)
    if stage=='extract':
        prior.write(folder/'compact-inventory.json',raw);raw=codec.decode(raw)
    return raw,bill


def prepare_replay(source=BASELINE):
    """Verify unchanged source and executable baseline before ANY paid dispatch."""
    protocol=json.loads((source/'protocol.json').read_text())
    spec=next(c for c in SPECS if c['id']==REPLAY_CASE)
    if spec!=next(c for c in protocol['specs'] if c['id']==REPLAY_CASE):raise ValueError('Replay request, roles or scorecard changed')
    for name in ('assembly_connections.py','construction_solid.py','construction.py'):
        key='Research/native_objects/'+name
        if hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()!=protocol['files_sha256'][key]:raise ValueError('Geometry executor changed')
    paths={'inventory':source/(REPLAY_CASE+'-extract/inventory.json'),
        'contract':source/(REPLAY_CASE+'-extract/contract.json'),
        'plan':source/(REPLAY_CASE+'-plan-0/compact-plan.json'),
        'compiled':source/(REPLAY_CASE+'-plan-0/compiled.json'),
        'lock':source/(REPLAY_CASE+'-plan-0/assembly-lock.json'),
        'bindings':source/(REPLAY_CASE+'-plan-0/arrangement-bindings.json')}
    data={k:json.loads(p.read_text()) for k,p in paths.items()}
    if arrangements.validate(data['inventory'],spec['request'],spec['roles'])!=data['contract']:raise ValueError('Replay interpretation changed')
    plan=pipeline.compact.expand(data['plan'],data['contract']);roles=sorted({p['role'] for p in plan['parts']})
    if not arrangements.coverage(data['contract'],plan,data['plan']['bindings'])['geometry_allowed']:raise ValueError('Replay coverage changed')
    _,report,compiled=pipeline.geometry.build(plan,roles,REPLAY_CASE,json.dumps(data['lock']))
    if compiled!=data['compiled']:raise ValueError('Baseline solved geometry changed')
    report['checks']+=pipeline.spatial.measurements(data['contract'],plan,data['plan']['bindings'],compiled)
    report['checks']+=arrangements.measurements(data['contract'],plan,data['plan']['bindings'],compiled)
    data['preservation']=repair.snapshot(report)
    data['audit']={'source_experiment':protocol['experiment'],'case':REPLAY_CASE,'source_attempt':0,
        'source_files_sha256':{str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()},
        'solved_geometry_identical':True,'no_new_generation_cost':True,'compiled_sha256':prior.digest(compiled)}
    data['spec']=spec;return data


def replay(stage,context,folder,data):
    spec=data['spec']
    if context.get('original_request')!=spec['request']:raise prior.CommandError('Replay request changed')
    if stage=='extract':
        if context.get('proposed_role_groups')!=spec['roles']:raise prior.CommandError('Replay roles changed')
        raw=data['inventory']
    else:
        for key,expected in (('requirements',data['contract']['inventory']),('requirement_hash',data['contract']['inventory_sha256']),
                ('spatial_rules',data['contract']['spatial_rules']),('assemblies',data['contract']['assemblies'])):
            if context.get(key)!=expected:raise prior.CommandError('Replay planning contract changed')
        raw=data['plan']
    meta={'replayed':True,'new_cost_nanos':0,'source_experiment':'assembly-010','source_stage':stage,'source_attempt':0,
        'source_output_sha256':prior.digest(raw)}
    prior.write(folder/'replay.json',meta);return deepcopy(raw),meta


def verify_replayed_execution(output,data):
    folder=output/(REPLAY_CASE+'-plan-0')
    for file,key in (('compiled.json','compiled'),('assembly-lock.json','lock'),('arrangement-bindings.json','bindings'),('repair-baseline.json','preservation')):
        if not (folder/file).exists() or json.loads((folder/file).read_text())!=data[key]:raise prior.CommandError('Replayed fan baseline changed before repair: '+file)


def codec_audit():
    rows=[]
    for case in ('cooling-fan-row','two-driver-speaker'):
        raw=json.loads((BASELINE/(case+'-extract/inventory.json')).read_text());compact=codec.encode(raw)
        full_size=len(json.dumps(raw,separators=(',',':')));compact_size=len(json.dumps(compact,separators=(',',':')))
        rows.append({'case':case,'lossless_roundtrip':codec.decode(compact)==raw,'named_json_characters':full_size,
            'compact_json_characters':compact_size,'character_reduction_fraction':1-compact_size/full_size,
            'token_reduction':'not measured; character counts are not token counts'})
    return rows


def assess(states,output):
    rows=previous.assess(states,output)
    for row in rows:
        if row['case']!='two-driver-speaker' or 'contract' not in states[row['case']]:continue
        contract=states[row['case']]['contract'];roles={e['id']:e['role'] for e in contract['inventory']['entities']}
        requirements={r['id']:r for r in contract['inventory']['requirements']}
        contact=any(rule['operator']=='on_surface' and rule['axis']=='+z' and
            requirements[rule['id']]['obligation']=='required' and
            roles.get(requirements[rule['id']]['subject'])=='Two loudspeaker drivers' and
            roles.get(requirements[rule['id']]['target'])=='Enclosure' for rule in contract['spatial_rules'])
        row['checks'].append({'kind':'original_front_face_requirement','passed':contact})
        row['predeclared_checks_passed']=all(c['passed'] for c in row['checks'])
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    data=prepare_replay();args.output.mkdir(parents=True,exist_ok=False)
    names=('assembly_followup.py','compact_requirements.py','repair_feedback.py','assembly_arrangements.py','arrangement_experiment.py',
        'arrangement_cases_010.json','spatial_requirements.py','spatial_experiment.py','requirements_experiment.py','requirement_meaning.py',
        'intent_requirements.py','compact_construction.py','assembly_connections.py','construction_solid.py','construction.py','meaning_experiment.py','ASSEMBLY_FOLLOWUP.md')
    files=[SOURCE/n for n in names]+[ROOT/'Orchestrator/spending.py']+[BASELINE/p for p in data['audit']['source_files_sha256']]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    prior.write(args.output/'protocol.json',{'experiment':BATCH.experiment,'specs':SPECS,'budget_nanos':BATCH.budget,
        'prior_upper_bound_nanos':BATCH.prior_upper_bound,'aggregate_limit_nanos':BATCH.aggregate_limit,'files_sha256':hashes,
        'policies':{s:selected(s) for s in ('extract','plan')},'arrangement_policy':arrangements.POLICY,
        'maximum_requirements':48,'lossless_row_transport':True,'surface_contact':'on_surface signed exterior planar face',
        'request_deadlines_seconds':{'extract':120,'plan':240},'maximum_plan_attempts':2,'execute':args.execute,
        'geometry_executor_changed':False,'paid_judge':False,'replay':data['audit'],'allowed_paid_operations':OPERATIONS})
    prior.write(args.output/'codec-audit.json',codec_audit());prior.write(args.output/'replay-audit.json',data['audit'])
    if not args.execute:return
    lock=open(ROOT/'.oryn-usage'/(BATCH.experiment+'.lock'),'a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
    if not key:raise prior.CommandError('Model connection unavailable')
    stopped=[]
    def model(case,stage,attempt,context,folder):
        if stopped:raise prior.CommandError('Batch stopped: '+stopped[0])
        if any(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h for n,h in hashes.items()):raise prior.CommandError('Frozen follow-up experiment changed')
        try:
            if case==REPLAY_CASE and attempt==0:return replay(stage,context,folder,data)
            if case==REPLAY_CASE:verify_replayed_execution(args.output,data)
            return request(case,stage,attempt,context,folder,ledger,key)
        except prior.CommandError as error:stopped.append(str(error));raise
    states=pipeline.execute(previous.items(),args.output,model,case_ids=CASES,preserve_passes=True)
    prior.write(args.output/'assessment.json',assess(states,args.output));summary=ledger.summary()
    prior.write(args.output/'spending.json',{'charged_and_held_nanos':BATCH.spent(ledger),'daily_limit_nanos':summary['daily_limit_nanos'],
        'daily_remaining_nanos':summary['remaining_nanos'],'actual_invoiced_cost':None,'stopped':stopped})
    print(json.dumps({'charged_and_held_usd':BATCH.spent(ledger)/1e9,'daily_remaining_usd':summary['remaining_nanos']/1e9,
        'cases':[{k:s[k] for k in ('case','status','geometry_executed')} for s in states.values()]}))

if __name__=='__main__':main()
