"""Spatial 008: frozen multi-object interpretation, coverage, geometry and bounded repair."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
from Research.native_objects import meaning_experiment as transport
from Research.native_objects import requirements_experiment as pipeline
from Research.native_objects import spatial_requirements as spatial

prior=transport.prior
ROOT=prior.ROOT
SOURCE=Path(__file__).parent
CASES=(*pipeline.CASES,'static-concept')
OPERATIONS=tuple(c+'/'+s+'/'+str(a) for c in CASES for s,count in [('extract',1),('plan',2)] for a in range(count))
BATCH=transport.Batch('spatial-008',OPERATIONS,1_500_000_000,3_100_000_000,5_000_000_000)


def items():
    result=json.loads((SOURCE/'results/planning-001.json').read_text())['items']
    result.append(json.loads((SOURCE/'results/construction-001/heldout-plan.json').read_text())['items'][0])
    case=next(c for c in transport.CASES if c['id']=='contrast_static')
    result.append({'case_id':'static-concept','request':case['request'],'candidate':{'plan':{
        'fidelity':'creative_concept','retrieval':'none','next_step':'propose_geometry',
        'components':[{'name':r} for r in case['roles']]}}})
    return result


def selected(stage):
    p=pipeline.selected(stage)
    if stage=='extract':p.update(max_output_tokens=3072,ceiling_nanos=45_000_000)
    p['profile']='spatial_research_'+stage
    return p


def body_for(stage,context):
    p=selected(stage)
    if stage=='extract':
        request=context['original_request'];roles=context['proposed_role_groups']
        content={'request':request,'entities':spatial.meaning.entity_catalog(roles),
                 'source_units':spatial.meaning.source_units(request)}
        schema=spatial.schema(request,roles);instructions=spatial.EXTRACT_INSTRUCTIONS
    else:
        content=pipeline.compact.planner_context(context);schema=pipeline.compact.SCHEMA
        instructions=pipeline.compact.INSTRUCTIONS+spatial.PLAN_INSTRUCTIONS+pipeline.compact.PLANNER_CONTEXT_INSTRUCTIONS
    return p,prior.body(p,instructions,json.dumps(content),schema,'oryn_spatial_'+stage)


def request(case,stage,attempt,context,folder,ledger,key):
    op=case+'/'+stage+'/'+str(attempt)
    if op not in BATCH.cases:raise prior.CommandError('Outside frozen spatial experiment')
    p,body=body_for(stage,context)
    return transport.dispatch(BATCH.operation_id(op),p,body,folder,ledger,key,batch=BATCH)


def assess(states):
    result=[]
    for case,state in states.items():
        if 'contract' not in state:continue
        c=state['contract'];roles={e['id']:e['role'] for e in c['inventory']['entities']}
        reqs={r['id']:r for r in c['inventory']['requirements']}
        row={'case':case,'rules':[dict(rule,subject_role=roles[reqs[rule['id']]['subject']],target_role=roles[reqs[rule['id']]['target']]) for rule in c.get('spatial_rules',[])],
             'meaning_complete':'unassessed','status':state['status'],'geometry_executed':state['geometry_executed']}
        source_id={'creative-concept':'original_lamp','generic-drone':'original_drone','static-concept':'contrast_static'}.get(case)
        if source_id:
            original=next(x for x in transport.CASES if x['id']==source_id)
            row['original_assertions']=transport.assess(original,c,state['admission'])
        if case=='generic-drone':
            needed={('radial_outward','Four arms','Central frame'),('outer_end','Four motors','Four arms'),('axis_aligned','Four propellers','Four motors')}
            row['spatial_intent_checks_passed']=needed<={(r['operator'],r['subject_role'],r['target_role']) for r in row['rules']}
        if case=='static-concept':row['spatial_intent_checks_passed']=any(r['operator']=='on_top' and r['subject_role']=='Open ring' and r['target_role']=='Base' for r in row['rules'])
        if case in ('generic-speaker','heldout-001'):
            row['no_unrequested_effect']=not any(r['predicate']=='capability' and r['value'] in ('animate','audio_output') for r in reqs.values())
            row['explode_preserved']=any(r['predicate']=='capability' and r['value']=='geometric_explode' for r in reqs.values())
        result.append(row)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    sources=[SOURCE/n for n in ('spatial_requirements.py','spatial_experiment.py','requirements_experiment.py',
        'requirement_meaning.py','intent_requirements.py','compact_construction.py','assembly_connections.py',
        'construction_solid.py','construction.py','meaning_experiment.py','meaning_cases_005.json',
        'results/planning-001.json','results/construction-001/heldout-plan.json')]+[ROOT/'Orchestrator/spending.py']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources};inputs=items()
    prior.write(args.output/'protocol.json',{'experiment':BATCH.experiment,'cases':CASES,
        'requests':[{k:i[k] for k in ('case_id','request')} for i in inputs if i['case_id'] in CASES],
        'budget_nanos':BATCH.budget,'prior_upper_bound_nanos':BATCH.prior_upper_bound,'aggregate_limit_nanos':BATCH.aggregate_limit,
        'files_sha256':hashes,'policies':{s:selected(s) for s in ('extract','plan')},'spatial_policy':spatial.POLICY,
        'extract_instructions_sha256':prior.digest(spatial.EXTRACT_INSTRUCTIONS),
        'plan_instructions_sha256':prior.digest(pipeline.compact.INSTRUCTIONS+spatial.PLAN_INSTRUCTIONS),
        'maximum_plan_attempts':2,'execute':args.execute,'model_reviewer':False})
    if not args.execute:return
    lock=open(ROOT/'.oryn-usage'/(BATCH.experiment+'.lock'),'a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
    if not key:raise prior.CommandError('Model connection unavailable')
    stopped=[]
    def model(case,stage,attempt,context,folder):
        if stopped:raise prior.CommandError('Batch stopped after admission/transport failure: '+stopped[0])
        if any(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h for n,h in hashes.items()):raise prior.CommandError('Frozen spatial experiment changed')
        try:return request(case,stage,attempt,context,folder,ledger,key)
        except prior.CommandError as error:stopped.append(str(error));raise
    states=pipeline.execute(inputs,args.output,model,case_ids=CASES)
    prior.write(args.output/'assessment.json',assess(states))
    summary=ledger.summary()
    prior.write(args.output/'spending.json',{'charged_and_held_nanos':BATCH.spent(ledger),'daily_limit_nanos':summary['daily_limit_nanos'],
        'daily_remaining_nanos':summary['remaining_nanos'],'actual_invoiced_cost':None,'stopped':stopped})
    print(json.dumps({'charged_and_held_usd':BATCH.spent(ledger)/1e9,'daily_remaining_usd':summary['remaining_nanos']/1e9,
        'cases':[{k:s[k] for k in ('case','status','geometry_executed')} for s in states.values()]}))

if __name__=='__main__':main()
