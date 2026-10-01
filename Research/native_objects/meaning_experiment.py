"""Bounded interpretation-only test. No planning, geometry or model judge calls."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from Research.native_objects import requirement_meaning as meaning
from Research.native_objects import solid_experiment as prior
from Research.native_objects.construction_experiment import NoRedirect

EXPERIMENT='meaning-005'
HOME=Path(__file__).parent
CASES=json.loads((HOME/'meaning_cases_005.json').read_text())
BUDGET=130_000_000
PRIOR_UPPER_BOUND=2_600_000_000
AGGREGATE_LIMIT=5_000_000_000


def selected():
    p=prior.chosen('construct');p.update(profile='meaning_research',effort='medium',max_output_tokens=3072,ceiling_nanos=45_000_000);return p


def operation_id(case):return prior.digest({'experiment':EXPERIMENT,'case':case})[:32]


def spent(ledger):return sum((ledger.get(operation_id(c['id'])) or {}).get('charged_nanos',0) for c in CASES)


def request(case,folder,ledger,key):
    if case not in CASES:raise prior.CommandError('Case outside frozen batch')
    if ledger.summary()['halted']:raise prior.CommandError('Shared ledger halted')
    ident=operation_id(case['id'])
    if ledger.get(ident):raise prior.CommandError('Already attempted; no retry')
    p=selected();body=prior.body(p,meaning.INSTRUCTIONS,json.dumps({'request':case['request'],'proposed_role_groups':case['roles']}),meaning.SCHEMA,'oryn_interpreted_requirements')
    prior.write(folder/'request.json',{'body':body,'body_sha256':prior.digest(body)})
    tokens=prior.count_input(key,body);cost=prior.quote_cost(p,tokens);now=int(time.time())
    if spent(ledger)+cost>BUDGET or PRIOR_UPPER_BOUND+spent(ledger)+cost>AGGREGATE_LIMIT:raise prior.CommandError('Research spending ceiling reached')
    q={'request_id':ident,'actor_id':'developer','provider':'openai','profile':p['profile'],'model':p['model'],'effort':p['effort'],
       'operation':EXPERIMENT,'fingerprint':prior.digest(body),'price_version':p['price_version'],'input_tokens':tokens,
       'max_output_tokens':p['max_output_tokens'],'reserved_nanos':cost,'ceiling_nanos':p['ceiling_nanos'],'created':now,'expires':min(now+120,prior.PRICE_EXPIRES)}
    ledger.create_quote(q);ledger.reserve(ident,'developer',q['fingerprint'],cost)
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    start=time.perf_counter()
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(req,timeout=120) as reply:raw=reply.read(262145)
        if len(raw)>262144:raise ValueError('Oversized response')
        response=json.loads(raw)
    except Exception as error:
        ledger.uncertain(ident);cause=error.reason if isinstance(error,urllib.error.URLError) else error
        prior.write(folder/'failure.json',{'category':'timeout' if isinstance(cause,TimeoutError) else 'response_unavailable','reservation_held':True,'automatic_retry':False})
        raise prior.CommandError('Response unavailable; reservation held') from None
    prior.write(folder/'response.json',response)
    try:incoming,outgoing,amount=prior.settled_usage(response,q)
    except prior.CommandError:ledger.uncertain(ident,halt=True);raise
    ledger.settle(ident,incoming,outgoing,amount,'completed' if response.get('status')=='completed' else 'invalid_response')
    meta={'operation_id':ident,'status':response.get('status'),'incomplete_details':response.get('incomplete_details'),'usage':response['usage'],'calculated_cost_nanos':amount,'dispatch_seconds':time.perf_counter()-start}
    prior.write(folder/'response-metadata.json',meta)
    return prior.parse(response),meta


def assess(case,contract,admission):
    """Predeclared benchmark assertions only. Never supplied to the compiler/model."""
    inventory=contract['inventory'];roles={e['id']:e['role'] for e in inventory['entities']}
    def matches(r,selector):
        for key,value in selector.items():
            if key=='subject_role':ok=roles.get(r['subject'])==value
            elif key=='target_role':ok=roles.get(r['target'])==value
            elif key=='value_pattern':ok=bool(re.search(value,r['value'],re.I))
            elif key=='predicate_any':ok=r['predicate'] in value
            else:ok=r.get(key)==value
            if not ok:return False
        return True
    checks=[];expected=case['expect']
    for selector in expected['must']:checks.append({'kind':'required_interpretation','selector':selector,'passed':any(matches(r,selector) for r in inventory['requirements'])})
    for selector in expected['forbid']:checks.append({'kind':'forbidden_interpretation','selector':selector,'passed':not any(matches(r,selector) for r in inventory['requirements'])})
    for scope in expected['exclusions']:checks.append({'kind':'waiver_preserved','domain':scope,'passed':any(e['domain']==scope for e in inventory['exclusions'])})
    if expected['planning_allowed'] is not None:checks.append({'kind':'expected_admission','expected':expected['planning_allowed'],'passed':admission['planning_allowed']==expected['planning_allowed']})
    return {'predeclared_checks_passed':all(c['passed'] for c in checks),'checks':checks,
            'meaning_fully_correct':'unassessed','scope':'Limited benchmark checks plus separate source review, not a semantic proof.'}


def execute(output,model):
    records=[]
    for case in CASES:
        folder=output/case['id'];folder.mkdir();record={'case':case['id'],'status':'running','geometry_executed':False};records.append(record)
        prior.write(output/'result.json',{'cases':records,'native_generation_goal_passed':False});print('Interpret '+case['id'],flush=True);start=time.perf_counter()
        try:
            raw,bill=model(case,folder);prior.write(folder/'inventory.json',raw)
            contract=meaning.validate(raw,case['request'],case['roles']);prior.write(folder/'contract.json',contract)
            admission=meaning.preflight(contract);prior.write(folder/'admission.json',admission)
            assessment=assess(case,contract,admission);prior.write(folder/'assessment.json',assessment)
            record.update(status='interpreted',billing=bill,planning_allowed=admission['planning_allowed'],predeclared_checks_passed=assessment['predeclared_checks_passed'],blocking=admission['blocking'])
        except (prior.CommandError,ValueError,KeyError,TypeError) as e:record.update(status='stopped',error=str(e))
        finally:record['elapsed_seconds']=time.perf_counter()-start;prior.write(output/'result.json',{'cases':records,'native_generation_goal_passed':False})
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    hashes={n:hashlib.sha256((HOME/n).read_bytes()).hexdigest() for n in ('assembly_connections.py','construction_solid.py','construction.py','requirement_meaning.py','meaning_cases_005.json')}
    prior.write(args.output/'protocol.json',{'experiment':EXPERIMENT,'budget_nanos':BUDGET,'prior_upper_bound_nanos':PRIOR_UPPER_BOUND,'aggregate_limit_nanos':AGGREGATE_LIMIT,'policy':selected(),'files_sha256':hashes,'instructions_sha256':prior.digest(meaning.INSTRUCTIONS),'schema_sha256':prior.digest(meaning.SCHEMA),'cases':CASES,'execute':args.execute})
    if not args.execute:return
    lock=open(prior.ROOT/'.oryn-usage'/(EXPERIMENT+'.lock'),'a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
    if not key:raise prior.CommandError('Model connection unavailable')
    def model(case,folder):
        if any(hashlib.sha256((HOME/n).read_bytes()).hexdigest()!=h for n,h in hashes.items()):raise prior.CommandError('Frozen experiment file changed')
        return request(case,folder,ledger,key)
    execute(args.output,model);print(json.dumps({'charged_and_held_usd':spent(ledger)/1e9}))

if __name__=='__main__':main()
