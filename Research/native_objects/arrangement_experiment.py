"""Assembly 010: explicit group decisions across three families, unchanged geometry."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
from Research.native_objects import spatial_experiment as previous
from Research.native_objects import assembly_arrangements as arrangements

prior=previous.prior
pipeline=previous.pipeline
transport=previous.transport
SOURCE=Path(__file__).parent
ROOT=previous.ROOT
SPECS=json.loads((SOURCE/'arrangement_cases_010.json').read_text())
CASES=tuple(c['id'] for c in SPECS)
OPERATIONS=tuple(c+'/'+s+'/'+str(a) for c in CASES for s,count in [('extract',1),('plan',2)] for a in range(count))
BATCH=transport.Batch('assembly-010',OPERATIONS,1_100_000_000,3_700_000_000,5_000_000_000)


def items():
    return [{'case_id':c['id'],'request':c['request'],'candidate':{'plan':{
        'fidelity':c['fidelity'],'retrieval':'none','next_step':'propose_geometry','components':[{'name':role} for role in c['roles']]}}} for c in SPECS]


def selected(stage):
    p=previous.selected(stage);p['profile']='assembly_arrangement_research_'+stage;return p


def body_for(stage,context):
    p=selected(stage)
    if stage=='extract':
        request=context['original_request'];roles=context['proposed_role_groups']
        content={'request':request,'entities':arrangements.spatial.meaning.entity_catalog(roles),
            'source_units':arrangements.spatial.meaning.source_units(request)}
        schema=arrangements.schema(request,roles);instructions=arrangements.EXTRACT_INSTRUCTIONS
    else:
        content=pipeline.compact.planner_context(context);schema=pipeline.compact.SCHEMA
        instructions=pipeline.compact.INSTRUCTIONS+arrangements.spatial.PLAN_INSTRUCTIONS+arrangements.PLAN_INSTRUCTIONS+pipeline.compact.PLANNER_CONTEXT_INSTRUCTIONS
    return p,prior.body(p,instructions,json.dumps(content),schema,'oryn_assembly_'+stage)


def request(case,stage,attempt,context,folder,ledger,key):
    op=case+'/'+stage+'/'+str(attempt)
    if op not in BATCH.cases:raise prior.CommandError('Outside frozen assembly experiment')
    p,body=body_for(stage,context)
    return transport.dispatch(BATCH.operation_id(op),p,body,folder,ledger,key,batch=BATCH,timeout=240 if stage=='plan' else 120)


def assess_contract(case,contract):
    """Hidden predeclared benchmark assertions, not a general semantic gate or judge."""
    expected=next(c for c in SPECS if c['id']==case)['expect']
    roles={e['id']:e['role'] for e in contract['inventory']['entities']};reqs=contract['inventory']['requirements'];checks=[]
    for spec in expected:
        ids={e for e,role in roles.items() if role==spec['role']}
        count=any(r['predicate']=='count' and r['subject'] in ids and int(r['value'])==spec['count'] and r['obligation']=='required' for r in reqs)
        matches=[a for a in contract['assemblies'] if set(a['members'])==ids]
        exact=any(a['placement']['pattern']==spec['pattern'] and a['placement']['axis']==spec['axis'] and
            roles.get(a['placement']['reference'],'')==spec['reference'] and a['orientation']['direction'] in spec['directions'] for a in matches)
        checks.append({'kind':'declared_group','role':spec['role'],'count_preserved':count,'placement_and_orientation_preserved':exact,'passed':count and exact})
    for capability in ('inspect','geometric_explode'):
        checks.append({'kind':'inspection_capability','value':capability,'passed':any(r['predicate']=='capability' and r['value']==capability and r['obligation']=='required' for r in reqs)})
    effects=[r for r in reqs if r['predicate']=='capability' and r['value'] in ('animate','audio_output') or r['mode']=='physical_verification']
    checks.append({'kind':'no_unrequested_effect_or_physics','passed':not effects})
    return {'predeclared_checks_passed':all(c['passed'] for c in checks),'checks':checks,
        'interpretation_complete':'unassessed','scope':'Specific conventional arrangements and supplied role catalogs; not proof of arbitrary understanding.'}


def assess(states,output):
    rows=[]
    for case,state in states.items():
        row={'case':case,'status':state['status'],'geometry_executed':state['geometry_executed']}
        if 'contract' in state:row.update(assess_contract(case,state['contract']))
        row['attempts']=[]
        for attempt in state['attempts']:
            folder=output/(case+'-plan-'+str(attempt['attempt']));report=folder/'relations.json'
            if not report.exists():continue
            checks=json.loads(report.read_text())['checks'];group=[c for c in checks if c['kind']=='assembly_arrangement'];connection=[c for c in checks if c['kind']=='connected_component']
            row['attempts'].append({'attempt':attempt['attempt'],'arrangements_pass':bool(group) and all(c['passed'] for c in group),
                'component_connectivity_pass':all(c['passed'] for c in connection),'all_declared_geometry_pass':all(c['passed'] for c in checks),
                'failed_checks':[c for c in checks if not c['passed']]})
        rows.append(row)
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    names=('assembly_arrangements.py','arrangement_experiment.py','arrangement_cases_010.json','spatial_requirements.py',
        'spatial_experiment.py','requirements_experiment.py','requirement_meaning.py','intent_requirements.py','compact_construction.py',
        'assembly_connections.py','construction_solid.py','construction.py','meaning_experiment.py','ASSEMBLY_EXPERIMENT.md')
    files=[SOURCE/n for n in names]+[ROOT/'Orchestrator/spending.py']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    prior.write(args.output/'protocol.json',{'experiment':BATCH.experiment,'specs':SPECS,'budget_nanos':BATCH.budget,
        'prior_upper_bound_nanos':BATCH.prior_upper_bound,'aggregate_limit_nanos':BATCH.aggregate_limit,'files_sha256':hashes,
        'policies':{s:selected(s) for s in ('extract','plan')},'arrangement_policy':arrangements.POLICY,
        'request_deadlines_seconds':{'extract':120,'plan':240},'maximum_plan_attempts':2,'execute':args.execute,
        'geometry_executor_changed':False,'paid_judge':False})
    if not args.execute:return
    lock=open(ROOT/'.oryn-usage'/(BATCH.experiment+'.lock'),'a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
    if not key:raise prior.CommandError('Model connection unavailable')
    stopped=[]
    def model(case,stage,attempt,context,folder):
        if stopped:raise prior.CommandError('Batch stopped: '+stopped[0])
        if any(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h for n,h in hashes.items()):raise prior.CommandError('Frozen assembly experiment changed')
        try:return request(case,stage,attempt,context,folder,ledger,key)
        except prior.CommandError as error:stopped.append(str(error));raise
    states=pipeline.execute(items(),args.output,model,case_ids=CASES)
    prior.write(args.output/'assessment.json',assess(states,args.output));summary=ledger.summary()
    prior.write(args.output/'spending.json',{'charged_and_held_nanos':BATCH.spent(ledger),'daily_remaining_nanos':summary['remaining_nanos'],
        'actual_invoiced_cost':None,'stopped':stopped})
    prior.write(args.output/'index.json',[{'name':p.name} for p in sorted(args.output.iterdir()) if p.is_dir() and (p/'package.json').exists()])
    (args.output/'index.html').write_text((SOURCE/'viewer.html').read_text())
    print(json.dumps({'charged_and_held_usd':BATCH.spent(ledger)/1e9,'daily_remaining_usd':summary['remaining_nanos']/1e9,
        'cases':[{k:s[k] for k in ('case','status','geometry_executed')} for s in states.values()]}))

if __name__=='__main__':main()
