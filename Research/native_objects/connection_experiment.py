"""Bounded current-model test of executable connections; no automatic retries."""
import argparse
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import time
import urllib.request
from Research.native_objects import assembly_connections as assembly
from Research.native_objects import solid_experiment as prior
from Research.native_objects.construction_experiment import NoRedirect

EXPERIMENT='connections-003'
CASES=prior.CASES
BUDGET=900_000_000
MAX_ATTEMPTS=2
PRIOR_RESEARCH_UPPER_BOUND=1_600_000_000  # Includes GPU estimates and uncertain 002 reservations.
AGGREGATE_LIMIT=5_000_000_000
TIMEOUT=240


def operation_id(case,attempt):return prior.digest({'experiment':EXPERIMENT,'case':case,'attempt':attempt})[:32]


def spent(ledger):
    return sum((ledger.get(operation_id(c,a)) or {}).get('charged_nanos',0) for c in CASES for a in range(MAX_ATTEMPTS))


def request_model(case,attempt,context,folder,ledger,key):
    if case not in CASES or not 0<=attempt<MAX_ATTEMPTS:raise prior.CommandError('Outside connection experiment')
    ident=operation_id(case,attempt)
    if ledger.get(ident):raise prior.CommandError('Already attempted; no transport retry')
    p=prior.chosen('construct');p['profile']='connection_research'
    body=prior.body(p,assembly.INSTRUCTIONS,json.dumps(context),assembly.SCHEMA,'oryn_connections')
    prior.write(folder/'request.json',{'body':body,'body_sha256':prior.digest(body)})
    tokens=prior.count_input(key,body);cost=prior.quote_cost(p,tokens);now=int(time.time())
    if spent(ledger)+cost>BUDGET or PRIOR_RESEARCH_UPPER_BOUND+spent(ledger)+cost>AGGREGATE_LIMIT:
        raise prior.CommandError('Research spending ceiling reached')
    q={'request_id':ident,'actor_id':'developer','provider':'openai','profile':p['profile'],
       'model':p['model'],'effort':p['effort'],'operation':EXPERIMENT,'fingerprint':prior.digest(body),
       'price_version':p['price_version'],'input_tokens':tokens,'max_output_tokens':p['max_output_tokens'],
       'reserved_nanos':cost,'ceiling_nanos':p['ceiling_nanos'],'created':now,'expires':min(now+120,prior.PRICE_EXPIRES)}
    ledger.create_quote(q);ledger.reserve(ident,'developer',q['fingerprint'],cost)
    request=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(body).encode(),
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    start=time.perf_counter()
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(request,timeout=TIMEOUT) as response:raw=response.read(262145)
        if len(raw)>262144:raise ValueError('Response size limit')
        result=json.loads(raw)
    except Exception as error:
        ledger.uncertain(ident)
        cause=error.reason if isinstance(error,prior.urllib.error.URLError) else error
        prior.write(folder/'failure.json',{'category':'timeout' if isinstance(cause,TimeoutError) else
            'http_error' if isinstance(error,prior.urllib.error.HTTPError) else 'response_unavailable',
            'dispatch_elapsed_seconds':time.perf_counter()-start,'reservation_held':True,'automatic_retry':False})
        raise prior.CommandError('Response unavailable; reservation held, no retry') from None
    prior.write(folder/'response.json',result)
    try:incoming,outgoing,calculated=prior.settled_usage(result,q)
    except prior.CommandError:ledger.uncertain(ident,halt=True);raise
    ledger.settle(ident,incoming,outgoing,calculated,'completed' if result.get('status')=='completed' else 'invalid_response')
    return prior.parse(result),{'operation_id':ident,'calculated_cost_nanos':calculated}


def run_case(item,output,model,renderer=prior.render):
    case=item['case_id'];plan=item['candidate']['plan'];history=[];locked=None;previous=None;feedback=None
    if plan['fidelity'] not in ('generic_design','creative_concept') or plan['retrieval']!='none' or plan['next_step']!='propose_geometry':
        return {'case':case,'status':'blocked_evidence'}
    roles=[x['name'] for x in plan['components']];start=time.perf_counter()
    for attempt in range(MAX_ATTEMPTS):
        folder=output/(case+'-'+str(attempt));folder.mkdir();record={'attempt':attempt,'status':'running'};history.append(record)
        prior.write(output/(case+'-history.json'),history);print('Connections '+case+' attempt '+str(attempt),flush=True)
        context={'request':item['request'],'role_groups':roles,'prior_design_assumptions':plan['assumptions']}
        if previous is not None:context.update(previous_proposal=previous,locked_requirements=json.loads(locked),application_feedback=feedback)
        try:
            before=time.perf_counter();proposal,bill=model(case,attempt,context,folder)
            record.update(planning_request_seconds=time.perf_counter()-before,billing=bill)
            prior.write(folder/'proposal.json',proposal)
            if locked is None:
                locked=assembly.freeze(proposal,roles)
                prior.write(output/(case+'-requirements.json'),json.loads(locked))
            before=time.perf_counter();compiled,connection_checks=assembly.compile_plan(proposal,roles,locked)
            record['connection_compile_seconds']=time.perf_counter()-before
            # build rechecks the same connections and all existing solid constraints.
            before=time.perf_counter();pkg,report,compiled=assembly.build(proposal,roles,case,locked)
            record['build_and_validation_seconds']=time.perf_counter()-before
            prior.write(folder/'compiled.json',compiled);prior.write(folder/'relations.json',report)
            prior.write_case(folder,pkg);renderer(folder)
            record.update(status='structural_candidate' if report['declared_relations_passed'] else 'structural_failure',
                          declared_numeric_pass=report['declared_relations_passed'],
                          render_ready_seconds_since_case_start=time.perf_counter()-start,
                          semantic_coverage='unassessed',visual_quality='unassessed',parts=len(pkg['parts']))
            if report['declared_relations_passed']:break
            previous=proposal;feedback={'failed_geometry_checks':[c for c in report['checks'] if not c['passed']]}
        except prior.CommandError as error:
            record.update(status='request_failed',error=str(error));break
        except (ValueError,KeyError,TypeError) as error:
            record.update(status='rejected',error=str(error))
            if locked is None:break
            previous=proposal;feedback={'compiler_error':str(error)}
        finally:prior.write(output/(case+'-history.json'),history)
    return {'case':case,'attempts':history,'elapsed_seconds':time.perf_counter()-start,
            'native_generation_goal_passed':False,'manual_repairs':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    items=json.loads(Path(__file__).with_name('results').joinpath('planning-001.json').read_text())['items']
    items.append(json.loads(Path(__file__).with_name('results').joinpath('construction-001/heldout-plan.json').read_text())['items'][0])
    protocol={'id':EXPERIMENT,'budget_nanos':BUDGET,'prior_research_upper_bound_nanos':PRIOR_RESEARCH_UPPER_BOUND,
       'aggregate_limit_nanos':AGGREGATE_LIMIT,'max_attempts':MAX_ATTEMPTS,'policy':prior.chosen('construct'),
       'timeout_seconds':TIMEOUT,'instructions_sha256':prior.digest(assembly.INSTRUCTIONS),'schema_sha256':prior.digest(assembly.SCHEMA),
       'requests':[{k:i[k] for k in ('case_id','request')} for i in items],'execute':args.execute}
    prior.write(args.output/'protocol.json',protocol)
    if not args.execute:return
    lock=open(prior.ROOT/'.oryn-usage'/(EXPERIMENT+'.lock'),'a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
    if not key:raise prior.CommandError('Research connection unavailable')
    def model(case,attempt,context,folder):return request_model(case,attempt,context,folder,ledger,key)
    results=[]
    for item in items:
        results.append(run_case(item,args.output,model));prior.write(args.output/'result.json',results)
        if ledger.summary()['halted']:break
    entries=[{'name':f.name} for f in args.output.iterdir() if f.is_dir() and (f/'package.json').exists()]
    prior.write(args.output/'index.json',entries);(args.output/'index.html').write_text(Path(__file__).with_name('viewer.html').read_text())
    print(json.dumps({'cases':len(results),'charged_and_held_usd':spent(ledger)/1e9}))

if __name__=='__main__':main()
