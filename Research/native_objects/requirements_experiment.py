"""Bounded request -> requirements -> compact plan -> coverage -> unchanged geometry."""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import time
import subprocess
import urllib.error
import urllib.request
from Research.native_objects import intent_requirements as intent
from Research.native_objects import requirement_meaning as meaning
from Research.native_objects import spatial_requirements as spatial
from Research.native_objects import compact_construction as compact
from Research.native_objects import assembly_connections as geometry
from Research.native_objects import solid_experiment as prior
from Research.native_objects.construction_experiment import NoRedirect

EXPERIMENT='requirements-004'
CASES=('creative-concept','generic-drone','generic-speaker','heldout-001')
BUDGET=500_000_000
PRIOR_RESEARCH_UPPER_BOUND=2_200_000_000
AGGREGATE_LIMIT=5_000_000_000
MAX_ATTEMPTS=2


def selected(stage):
    p=prior.chosen('construct');p.update(profile='intent_research_'+stage,effort='medium',
        max_output_tokens=4096 if stage=='extract' else 12288,
        ceiling_nanos=55_000_000 if stage=='extract' else 160_000_000)
    return p


def operation_id(case,stage,attempt):return prior.digest({'experiment':EXPERIMENT,'case':case,'stage':stage,'attempt':attempt})[:32]


def spent(ledger):
    return sum((ledger.get(operation_id(c,s,a)) or {}).get('charged_nanos',0)
               for c in CASES for s,attempts in [('extract',1),('plan',2)] for a in range(attempts))


def request_model(case,stage,attempt,context,folder,ledger,key):
    if case not in CASES or stage not in ('extract','plan') or not 0<=attempt<(1 if stage=='extract' else 2):raise prior.CommandError('Outside requirement experiment')
    ident=operation_id(case,stage,attempt)
    if ledger.get(ident):raise prior.CommandError('Already attempted; no transport retry')
    p=selected(stage);instructions,schema=(intent.EXTRACT_INSTRUCTIONS,intent.REQUIREMENTS_SCHEMA) if stage=='extract' else (compact.INSTRUCTIONS,compact.SCHEMA)
    body=prior.body(p,instructions,json.dumps(context),schema,'oryn_'+stage+'_requirements')
    prior.write(folder/'request.json',{'body':body,'body_sha256':prior.digest(body)})
    tokens=prior.count_input(key,body);cost=prior.quote_cost(p,tokens);now=int(time.time())
    if spent(ledger)+cost>BUDGET or PRIOR_RESEARCH_UPPER_BOUND+spent(ledger)+cost>AGGREGATE_LIMIT:raise prior.CommandError('Research spending ceiling reached')
    q={'request_id':ident,'actor_id':'developer','provider':'openai','profile':p['profile'],
       'model':p['model'],'effort':p['effort'],'operation':EXPERIMENT+'_'+stage,'fingerprint':prior.digest(body),
       'price_version':p['price_version'],'input_tokens':tokens,'max_output_tokens':p['max_output_tokens'],
       'reserved_nanos':cost,'ceiling_nanos':p['ceiling_nanos'],'created':now,'expires':min(now+120,prior.PRICE_EXPIRES)}
    ledger.create_quote(q);ledger.reserve(ident,'developer',q['fingerprint'],cost)
    request=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(body).encode(),
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    start=time.perf_counter()
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(request,timeout=240) as response:raw=response.read(262145)
        if len(raw)>262144:raise ValueError('Response size limit')
        result=json.loads(raw)
    except Exception as error:
        ledger.uncertain(ident);cause=error.reason if isinstance(error,urllib.error.URLError) else error
        prior.write(folder/'failure.json',{'category':'timeout' if isinstance(cause,TimeoutError) else
            'http_error' if isinstance(error,urllib.error.HTTPError) else 'response_unavailable',
            'dispatch_seconds':time.perf_counter()-start,'reservation_held':True,'automatic_retry':False})
        raise prior.CommandError('Response unavailable; reservation held, no retry') from None
    prior.write(folder/'response.json',result)
    try:incoming,outgoing,calculated=prior.settled_usage(result,q)
    except prior.CommandError:ledger.uncertain(ident,halt=True);raise
    ledger.settle(ident,incoming,outgoing,calculated,'completed' if result.get('status')=='completed' else 'invalid_response')
    reasoning=result['usage'].get('output_tokens_details',{}).get('reasoning_tokens')
    prior.write(folder/'response-metadata.json',{'status':result.get('status'),'incomplete_details':result.get('incomplete_details'),
        'usage':result['usage'],'operation_id':ident,'calculated_cost_nanos':calculated,'dispatch_seconds':time.perf_counter()-start})
    return prior.parse(result),{'operation_id':ident,'calculated_cost_nanos':calculated,'output_tokens':outgoing,'reasoning_tokens':reasoning}


def evaluate_candidate(raw,contract,folder,case,locked=None,builder=geometry.build,renderer=prior.render):
    plan=compact.expand(raw,contract)
    gate=(spatial.coverage if 'spatial_rules' in contract else meaning.coverage if contract.get('interpretation_version') else intent.coverage)(contract,plan,raw['bindings']);prior.write(folder/'coverage.json',gate)
    prior.write(folder/'expanded.json',plan)
    if not gate['coverage_complete']:
        return {'status':'coverage_failed','geometry_executed':False,'feedback':{'coverage_errors':gate['errors']}},locked
    if not gate['geometry_allowed']:
        return {'status':'unsupported_required','geometry_executed':False,'blocking':gate['blocking_unsupported']},locked
    roles=sorted({p['role'] for p in plan['parts']})
    if not plan['parts']:raise ValueError('No executable assembly remains')
    frozen=locked or geometry.freeze(plan,roles)
    prior.write(folder/'assembly-lock.json',json.loads(frozen))
    prior.write(folder/'execution-started.json',{'coverage_complete':True,'geometry_allowed':True})
    before=time.perf_counter();pkg,report,compiled=builder(plan,roles,case,frozen)
    if 'spatial_rules' in contract:
        report['checks']+=spatial.measurements(contract,plan,raw['bindings'],compiled)
        report['declared_relations_passed']=all(c['passed'] for c in report['checks'])
        report['spatial_policy_sha256']=contract['spatial_policy_sha256']
    seconds=time.perf_counter()-before
    prior.write(folder/'relations.json',report);prior.write(folder/'compiled.json',compiled)
    # Existing inspectors consume the expanded proposal, not compact transport.
    prior.write(folder/'proposal.json',plan);prior.write_case(folder,pkg);renderer(folder)
    status='structural_candidate' if report['declared_relations_passed'] else 'geometry_failed'
    return {'status':status,'geometry_executed':True,'geometry_and_validation_seconds':seconds,
            'declared_numeric_pass':report['declared_relations_passed'],'coverage_complete':True,
            'feedback':{'failed_geometry_checks':[c for c in report['checks'] if not c['passed']]},'parts':len(pkg['parts'])},frozen


def execute(items,output,model,renderer=prior.render,case_ids=CASES):
    order={i['case_id']:i for i in items}
    if len(set(case_ids))!=len(case_ids) or any(c not in order for c in case_ids):raise ValueError("Invalid case subset")
    states={};started=time.perf_counter()
    def save():prior.write(output/'result.json',{'cases':list(states.values()),'native_generation_goal_passed':False,'elapsed_seconds':time.perf_counter()-started})
    # All initial attempts precede repairs; one difficult case cannot consume the whole budget first.
    for case in case_ids:
        item=order[case];p=item['candidate']['plan'];state={'case':case,'request':item['request'],'attempts':[],'geometry_executed':False};states[case]=state
        if p['fidelity'] not in ('generic_design','creative_concept') or p['retrieval']!='none' or p['next_step']!='propose_geometry':state['status']='blocked_evidence';save();continue
        folder=output/(case+'-extract');folder.mkdir();before=time.perf_counter();state['status']='extracting';save();print('Requirements '+case,flush=True)
        try:
            raw,bill=model(case,'extract',0,{'original_request':item['request'],'proposed_role_groups':[c['name'] for c in p['components']]},folder)
            prior.write(folder/'inventory.json',raw)
            validator=intent.validate_inventory
            if 'exclusions' in raw:
                validator=meaning.validate
                if any('source' in r for r in raw.get('requirements',[])):
                    validator=meaning.validate_source_output if 'entities' in raw else meaning.validate_bound_source_output
            if 'spatial' in raw:validator=spatial.validate
            contract=validator(raw,item['request'],[c['name'] for c in p['components']]);prior.write(folder/'contract.json',contract)
            state.update(status='requirements_ready',extraction_billing=bill,contract=contract)
            if contract.get('interpretation_version'):
                admission=(spatial.preflight if 'spatial_rules' in contract else meaning.preflight)(contract);prior.write(folder/'admission.json',admission);state['admission']=admission
                if not admission['planning_allowed']:state['status']='unsupported_before_planning'
        except (prior.CommandError,ValueError,KeyError,TypeError) as e:state.update(status='extraction_failed',error=str(e))
        finally:state['extraction_seconds']=time.perf_counter()-before;save()
    for attempt in range(MAX_ATTEMPTS):
        for case in case_ids:
            state=states[case]
            if state['status'] not in ('requirements_ready','coverage_failed','geometry_failed','planning_rejected'):continue
            folder=output/(case+'-plan-'+str(attempt));folder.mkdir();before=time.perf_counter();record={'attempt':attempt,'status':'planning','geometry_executed':False};state['attempts'].append(record);save()
            print('Plan '+case+' attempt '+str(attempt),flush=True)
            context={'original_request':state['request'],'requirements':state['contract']['inventory'],
                     'requirement_hash':state['contract']['inventory_sha256']}
            if 'spatial_rules' in state['contract']:
                context.update(spatial_rules=state['contract']['spatial_rules'],spatial_policy=spatial.POLICY)
            if attempt:context.update(previous_compact_plan=state.get('previous'),application_feedback=state.get('feedback'),locked_assembly=state.get('locked'))
            try:
                raw,bill=model(case,'plan',attempt,context,folder);record.update(planning_seconds=time.perf_counter()-before,billing=bill)
                prior.write(folder/'compact-plan.json',raw);state['previous']=raw
                result,locked=evaluate_candidate(raw,state['contract'],folder,case,state.get('locked'),renderer=renderer)
                record.update(result);state.update(status=result['status'],feedback=result.get('feedback'),locked=locked)
                state['geometry_executed']=state['geometry_executed'] or result['geometry_executed']
            except prior.CommandError as e:record.update(status='request_failed',error=str(e));state['status']='request_failed'
            except (ValueError,KeyError,TypeError,subprocess.SubprocessError) as e:
                record.update(status='planning_rejected',error=str(e));state.update(status='planning_rejected',feedback={'compiler_error':str(e)})
                # No automatic retry of an incomplete/invalid provider response.
                if not (folder/'compact-plan.json').exists():state['status']='response_invalid'
            finally:
                record['geometry_executed']=(folder/'execution-started.json').exists()
                state['geometry_executed']=state['geometry_executed'] or record['geometry_executed']
                if (folder/'assembly-lock.json').exists():state['locked']=(folder/'assembly-lock.json').read_text()
                record['attempt_elapsed_seconds']=time.perf_counter()-before;save()
    # Keep large revision context local; result file still retains immutable contracts and all measurements.
    for state in states.values():
        for key in ('previous','feedback','locked'):state.pop(key,None)
    if 'exact-product' in order:states['exact-product']={'case':'exact-product','status':'blocked_evidence','geometry_executed':False}
    save()
    entries=[{'name':f.name} for f in output.iterdir() if f.is_dir() and (f/'package.json').exists()]
    prior.write(output/'index.json',entries);(output/'index.html').write_text(Path(__file__).with_name('viewer.html').read_text())
    return states


def saved_extractions(source):
    """Recover only never-planned cases from unchanged completed provider responses."""
    states=json.loads((source/'result.json').read_text())['cases'];replayed={}
    if any(s['status']=='extracting' or any(a['status']=='planning' for a in s.get('attempts',[])) for s in states):
        raise ValueError('Source experiment is still running')
    for state in states:
        if state['status']!='extraction_failed' or state.get('attempts'):continue
        case=state['case'];folder=source/(case+'-extract')
        if case not in CASES or not (folder/'inventory.json').exists():continue
        response=json.loads((folder/'response.json').read_text());raw=prior.parse(response)
        if raw!=json.loads((folder/'inventory.json').read_text()):raise ValueError('Saved extraction changed')
        meta=json.loads((folder/'response-metadata.json').read_text())
        replayed[case]={'raw':raw,'request':state['request'],'response_sha256':hashlib.sha256((folder/'response.json').read_bytes()).hexdigest(),
                       'original_error':state['error'],'billing':{'replayed':True,'new_cost_nanos':0,'original_operation_id':meta['operation_id']}}
    if not replayed:raise ValueError('No completed, never-planned extraction to revalidate')
    return replayed


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--revalidate-from',type=Path);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    home=Path(__file__).parent;items=json.loads((home/'results/planning-001.json').read_text())['items']
    items.append(json.loads((home/'results/construction-001/heldout-plan.json').read_text())['items'][0])
    replayed=saved_extractions(args.revalidate_from) if args.revalidate_from else {}
    for item in items:
        if item['case_id'] in replayed and item['request']!=replayed[item['case_id']]['request']:raise ValueError('Original request changed')
    hashes={name:hashlib.sha256((home/name).read_bytes()).hexdigest() for name in ('assembly_connections.py','construction_solid.py','construction.py')}
    prior.write(args.output/'protocol.json',{'id':EXPERIMENT,'budget_nanos':BUDGET,'prior_research_upper_bound_nanos':PRIOR_RESEARCH_UPPER_BOUND,
       'aggregate_limit_nanos':AGGREGATE_LIMIT,'policies':{s:selected(s) for s in ('extract','plan')},'geometry_sha256':hashes,
       'extract_instructions_sha256':prior.digest(intent.EXTRACT_INSTRUCTIONS),'plan_instructions_sha256':prior.digest(compact.INSTRUCTIONS),
       'requirement_schema_sha256':prior.digest(intent.REQUIREMENTS_SCHEMA),'plan_schema_sha256':prior.digest(compact.SCHEMA),
       'max_plan_attempts':2,'execute':args.execute,'revalidated_extractions':replayed,'requests':[{k:i[k] for k in ('case_id','request')} for i in items]})
    if not args.execute:return
    lock=open(prior.ROOT/'.oryn-usage'/(EXPERIMENT+'.lock'),'a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
    if not key:raise prior.CommandError('Research connection unavailable')
    def model(case,stage,attempt,context,folder):
        if ledger.summary()['halted']:raise prior.CommandError('Shared ledger halted')
        for name,expected in hashes.items():
            if hashlib.sha256((home/name).read_bytes()).hexdigest()!=expected:raise prior.CommandError('Frozen geometry executor changed')
        if stage=='extract' and case in replayed:return deepcopy(replayed[case]['raw']),replayed[case]['billing']
        return request_model(case,stage,attempt,context,folder,ledger,key)
    execute(items,args.output,model,case_ids=tuple(replayed) if replayed else CASES)
    print(json.dumps({'charged_and_held_usd':spent(ledger)/1e9}))

if __name__=='__main__':main()
