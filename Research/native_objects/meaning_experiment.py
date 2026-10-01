"""Bounded interpretation-only test. No planning, geometry or model judge calls."""
import argparse
from dataclasses import dataclass
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
SOURCE_DIR=Path(__file__).parent
CASES=json.loads((SOURCE_DIR/'meaning_cases_005.json').read_text())
BUDGET=130_000_000
PRIOR_UPPER_BOUND=2_600_000_000
AGGREGATE_LIMIT=5_000_000_000


def selected():
    p=prior.chosen('construct');p.update(profile='meaning_research',effort='medium',max_output_tokens=3072,ceiling_nanos=45_000_000);return p


def operation_id(case):return DEFAULT_BATCH.operation_id(case)


FOLLOWUP_ID='source-reference-followup'
FOLLOWUP_CASES=('contrast_motion','original_drone')

@dataclass(frozen=True)
class Batch:
    experiment: str
    cases: tuple
    budget: int
    prior_upper_bound: int
    aggregate_limit: int

    def operation_id(self,case):
        return prior.digest({'experiment':self.experiment,'case':case})[:32]

    def spent(self,ledger):
        return sum((ledger.get(self.operation_id(c)) or {}).get('charged_nanos',0) for c in self.cases)


DEFAULT_BATCH=Batch(EXPERIMENT,tuple(c['id'] for c in CASES)+(FOLLOWUP_ID,),BUDGET,PRIOR_UPPER_BOUND,AGGREGATE_LIMIT)


def spent(ledger):return DEFAULT_BATCH.spent(ledger)


def failure_category(error):
    # Classify only known provider codes, never expose exception text or response bodies.
    if isinstance(error,urllib.error.HTTPError):
        try:
            raw=error.read(8193)
            if len(raw)<=8192:
                code=json.loads(raw).get('error',{}).get('code')
                if code in ('insufficient_quota','billing_hard_limit_reached','billing_not_active'):
                    return 'provider_funding_required'
                if code=='rate_limit_exceeded':return 'rate_limited'
        except (ValueError,TypeError,AttributeError,OSError):pass
        return 'http_error'
    cause=error.reason if isinstance(error,urllib.error.URLError) else error
    return 'timeout' if isinstance(cause,TimeoutError) else 'response_unavailable'


def request(case,folder,ledger,key):
    if case not in CASES:raise prior.CommandError('Case outside frozen batch')
    if ledger.summary()['halted']:raise prior.CommandError('Shared ledger halted')
    ident=operation_id(case['id'])
    if ledger.get(ident):raise prior.CommandError('Already attempted; no retry')
    p=selected();body=prior.body(p,meaning.INSTRUCTIONS,json.dumps({'request':case['request'],'proposed_role_groups':case['roles']}),meaning.SCHEMA,'oryn_interpreted_requirements')
    return dispatch(ident,p,body,folder,ledger,key)


def dispatch(ident,p,body,folder,ledger,key,batch=None,timeout=120):
    if timeout not in (120,240):raise prior.CommandError('Unreviewed request deadline')
    batch=batch or DEFAULT_BATCH
    allowed={batch.operation_id(c) for c in batch.cases}
    if ident not in allowed:raise prior.CommandError('Operation outside frozen bounds')
    if ledger.get(ident):raise prior.CommandError('Already attempted; no retry')
    if ledger.summary()['halted']:raise prior.CommandError('Shared ledger halted')
    prior.write(folder/'request.json',{'body':body,'body_sha256':prior.digest(body)})
    tokens=prior.count_input(key,body);cost=prior.quote_cost(p,tokens);now=int(time.time())
    used=batch.spent(ledger)
    if used+cost>batch.budget or batch.prior_upper_bound+used+cost>batch.aggregate_limit:raise prior.CommandError('Research spending ceiling reached')
    q={'request_id':ident,'actor_id':'developer','provider':'openai','profile':p['profile'],'model':p['model'],'effort':p['effort'],
       'operation':batch.experiment,'fingerprint':prior.digest(body),'price_version':p['price_version'],'input_tokens':tokens,
       'max_output_tokens':p['max_output_tokens'],'reserved_nanos':cost,'ceiling_nanos':p['ceiling_nanos'],'created':now,'expires':min(now+120,prior.PRICE_EXPIRES)}
    ledger.create_quote(q);ledger.reserve(ident,'developer',q['fingerprint'],cost)
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    start=time.perf_counter()
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(req,timeout=timeout) as reply:raw=reply.read(262145)
        if len(raw)>262144:raise ValueError('Oversized response')
        response=json.loads(raw)
    except Exception as error:
        ledger.uncertain(ident);category=failure_category(error)
        prior.write(folder/'failure.json',{'category':category,'reservation_held':True,'automatic_retry':False})
        message='Provider funding required; top up the API account before continuing' if category=='provider_funding_required' else 'Response unavailable; reservation held'
        raise prior.CommandError(message) from None
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



def followup_spec():
    chosen=[c for c in CASES if c['id'] in FOLLOWUP_CASES]
    policy=selected();policy['max_output_tokens']=2432
    schema=meaning.construction.object_schema({c['id']:meaning.source_schema(c['request']) for c in chosen})
    content={'cases':[{k:c[k] for k in ('id','request','roles')}|{'source_units':meaning.source_units(c['request'])} for c in chosen]}
    body=prior.body(policy,meaning.SOURCE_INSTRUCTIONS,json.dumps(content),schema,'oryn_source_bound_interpretation')
    return chosen,policy,body


def execute_followup(output,model):
    chosen,_,_=followup_spec();records=[]
    try:
        raw,meta=model();prior.write(output/'batch-output.json',raw)
    except (prior.CommandError,ValueError,KeyError,TypeError) as e:
        result={'status':'stopped','error':str(e),'geometry_executed':False};prior.write(output/'result.json',result);return result
    for case in chosen:
        folder=output/case['id'];folder.mkdir();record={'case':case['id'],'geometry_executed':False};records.append(record)
        try:
            original=raw[case['id']];prior.write(folder/'inventory.json',original)
            contract=meaning.validate_source_output(original,case['request'],case['roles']);prior.write(folder/'contract.json',contract)
            admission=meaning.preflight(contract);prior.write(folder/'admission.json',admission)
            assessment=assess(case,contract,admission);prior.write(folder/'assessment.json',assessment)
            record.update(status='interpreted',planning_allowed=admission['planning_allowed'],predeclared_checks_passed=assessment['predeclared_checks_passed'],blocking=admission['blocking'])
        except (ValueError,KeyError,TypeError) as e:record.update(status='stopped',error=str(e))
    result={'cases':records,'billing':meta,'native_generation_goal_passed':False,'paired_followup':True};prior.write(output/'result.json',result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--source-followup',action='store_true');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    hashes={n:hashlib.sha256((SOURCE_DIR/n).read_bytes()).hexdigest() for n in ('assembly_connections.py','construction_solid.py','construction.py','requirement_meaning.py','meaning_cases_005.json','intent_requirements.py','meaning_experiment.py')}
    prior.write(args.output/'protocol.json',{'experiment':EXPERIMENT,'budget_nanos':BUDGET,'prior_upper_bound_nanos':PRIOR_UPPER_BOUND,'aggregate_limit_nanos':AGGREGATE_LIMIT,'policy':selected(),'files_sha256':hashes,'instructions_sha256':prior.digest(meaning.INSTRUCTIONS),'schema_sha256':prior.digest(meaning.SCHEMA),'cases':CASES,'execute':args.execute,'source_followup':args.source_followup,'followup_spec':followup_spec()[1:] if args.source_followup else None})
    if not args.execute:return
    lock=open(prior.ROOT/'.oryn-usage'/(EXPERIMENT+'.lock'),'a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
    if not key:raise prior.CommandError('Model connection unavailable')
    def model(case,folder):
        if any(hashlib.sha256((SOURCE_DIR/n).read_bytes()).hexdigest()!=h for n,h in hashes.items()):raise prior.CommandError('Frozen experiment file changed')
        return request(case,folder,ledger,key)
    if args.source_followup:
        _,p,body=followup_spec()
        def followup():
            if any(hashlib.sha256((SOURCE_DIR/n).read_bytes()).hexdigest()!=h for n,h in hashes.items()):raise prior.CommandError('Frozen experiment changed')
            return dispatch(operation_id(FOLLOWUP_ID),p,body,args.output,ledger,key)
        execute_followup(args.output,followup)
    else:execute(args.output,model)
    print(json.dumps({'charged_and_held_usd':spent(ledger)/1e9}))

if __name__=='__main__':main()
