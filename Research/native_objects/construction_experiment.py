"""Research-only model -> bounded operations -> existing package; no output repairs."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Orchestrator'))
from cognitive_providers import count_input,NoRedirect
from cognition import CommandError
from credential_store import MacKeychain
from spending import policy,quote_cost,settled_usage,digest,PRICE_EXPIRES
from usage_ledger import UsageLedger
from Research.native_objects.construction import INSTRUCTIONS,SCHEMA,build,relations
from Research.native_objects.experiment import write_case,evaluate

EXPERIMENT='construction-001'
ALLOWED=('generic-drone','generic-speaker','creative-concept','heldout-001')

def write(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');tmp.replace(path)


def selected_policy(now):
    # Dedicated research allocation using already-reviewed model/rates. Production
    # profiles and the per-investigation limit are unchanged. Four calls <= $0.48.
    chosen=deepcopy(policy('openai','planning',now))
    chosen.update(profile='construction_research',max_output_tokens=8192,ceiling_nanos=120_000_000)
    return chosen


def body_for(item,chosen):
    plan=item['candidate']['plan']
    return {'model':chosen['model'],'store':False,'max_output_tokens':chosen['max_output_tokens'],
        'service_tier':'default','reasoning':{'effort':chosen['effort']},
        'input':[{'role':'developer','content':INSTRUCTIONS},{'role':'user','content':json.dumps(
            {'request':item['request'],'role_groups':[c['name'] for c in plan['components']],
             'prior_design_assumptions':plan['assumptions']},allow_nan=False)}],
        'text':{'format':{'type':'json_schema','name':'oryn_construction_experiment','strict':True,'schema':SCHEMA}}}


def send(key,body):
    request=urllib.request.Request('https://api.openai.com/v1/responses',
        data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(request,timeout=120) as response:raw=response.read(131073)
    if len(raw)>131072:raise ValueError('Oversized response')
    return json.loads(raw)


def generate(item,ledger,key,chosen,counter=count_input,sender=send):
    ident=digest({'experiment':EXPERIMENT,'case':item['case_id']})[:32]
    if item['case_id'] not in ALLOWED:raise CommandError('Case outside frozen batch')
    if ledger.get(ident):raise CommandError('Case already attempted; no retry')
    body=body_for(item,chosen);count=counter(key,body);amount=quote_cost(chosen,count);now=int(time.time())
    q={'request_id':ident,'actor_id':'developer','provider':'openai','profile':chosen['profile'],
       'model':chosen['model'],'effort':chosen['effort'],'operation':'construction_experiment',
       'fingerprint':digest(body),'price_version':chosen['price_version'],'input_tokens':count,
       'max_output_tokens':chosen['max_output_tokens'],'reserved_nanos':amount,
       'ceiling_nanos':chosen['ceiling_nanos'],'created':now,'expires':min(now+120,PRICE_EXPIRES)}
    ledger.create_quote(q);ledger.reserve(ident,'developer',q['fingerprint'],amount)
    try:result=sender(key,body)
    except Exception:
        ledger.uncertain(ident);raise CommandError('Response unavailable; reservation held, no retry') from None
    try:incoming,outgoing,cost=settled_usage(result,q)
    except CommandError:ledger.uncertain(ident,halt=True);raise
    # Retain malformed/incomplete output as evidence too; caller validates, never rescues.
    ledger.settle(ident,incoming,outgoing,cost,'completed' if result.get('status')=='completed' else 'invalid_response')
    return result,{'operation_id':ident,'calculated_cost_nanos':cost,'invoice_cost_nanos':None,'body_sha256':digest(body)}


def parse(result):
    if result.get('status')!='completed':raise ValueError('Incomplete generation')
    messages=[c for i in result['output'] if i.get('type')=='message' for c in i['content']]
    if any(c.get('type')=='refusal' for c in messages):raise ValueError('Model refused')
    texts=[c['text'] for c in messages if c.get('type')=='output_text']
    if len(texts)!=1:raise ValueError('Expected one structured response')
    return json.loads(texts[0])


def execute(items,output,ledger,key,chosen):
    index=[];records=[]
    for item in items:
        case=item['case_id'];plan=item['candidate']['plan'];start=time.perf_counter()
        record={'case_id':case,'request':item['request'],'planning_source_replayed':True,
                'status':'running','manual_repairs':0,'retry_count':0,'geometry_quality':'not_assessed'}
        records.append(record);write(output/'run.json',records)
        if plan['fidelity'] not in ('generic_design','creative_concept') or plan['next_step']!='propose_geometry' or plan['retrieval']!='none':
            record.update(status='blocked_evidence',reason='Existing exact-product/evidence gate retained.')
            write(output/'run.json',records);continue
        print('Constructing '+case,flush=True)
        folder=output/case;folder.mkdir()
        try:
            response,billing=generate(item,ledger,key,chosen)
            write(folder/'response.json',response);record.update(billing=billing)
            record['construction_request_seconds']=time.perf_counter()-start
            proposal=parse(response);write(folder/'proposal.json',proposal)
            roles=[c['name'] for c in plan['components']]
            before=time.perf_counter();coarse=build(proposal,roles,case,12)
            report=relations(proposal,coarse)
            write_case(output/(case+'-coarse'),coarse);write(folder/'relations-coarse.json',report)
            record['coarse_build_validate_export_seconds']=time.perf_counter()-before
            record['coarse_file_ready_seconds']=time.perf_counter()-start
            before=time.perf_counter();fine=build(proposal,roles,case,24)
            fine_report=relations(proposal,fine)
            write_case(output/(case+'-fine'),fine);write(folder/'relations-fine.json',fine_report)
            record['fine_build_validate_export_seconds']=time.perf_counter()-before
            record['fine_file_ready_seconds']=time.perf_counter()-start
            record.update(status='completed',parts=len(coarse['parts']),
                declared_relations_passed=report['declared_relations_passed'] and fine_report['declared_relations_passed'],
                first_useful_seconds=None,client_ready_seconds=None,
                refinement_kind='deterministic_tessellation_only_not_generative_polish',
                generative_refinement_seconds=None,native_generation_goal_passed=False)
            for stage,pkg in [('coarse',coarse),('fine',fine)]:index.append({'name':case+'-'+stage,'report':evaluate(pkg)})
        except (CommandError,ValueError,KeyError,TypeError) as error:
            record.update(status='failed',error=str(error),elapsed_seconds=time.perf_counter()-start)
            ident=digest({'experiment':EXPERIMENT,'case':case})[:32];row=ledger.get(ident)
            if row:record['ledger_status']={k:row[k] for k in ('status','outcome','charged_nanos')}
        write(output/'run.json',records)
        if ledger.summary()['halted']:break
    write(output/'index.json',index)
    (output/'index.html').write_text(Path(__file__).with_name('viewer.html').read_text())
    print(json.dumps([{'case':r['case_id'],'status':r['status'],'relations':r.get('declared_relations_passed')} for r in records]))
    return records


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plans',type=Path,default=Path(__file__).with_name('results')/'planning-001.json')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true')
    args=p.parse_args();raw=args.plans.read_bytes();items=json.loads(raw)['items'];chosen=selected_policy(int(time.time()))
    ids=[i['case_id'] for i in items]
    if len(ids)!=len(set(ids)) or any(i not in (*ALLOWED,'exact-product') for i in ids):p.error('Unexpected or duplicate case IDs')
    args.output.mkdir(parents=True,exist_ok=False)
    write(args.output/'protocol.json',{'experiment':EXPERIMENT,'plans_sha256':hashlib.sha256(raw).hexdigest(),
        'instructions_sha256':digest(INSTRUCTIONS),'schema_sha256':digest(SCHEMA),'policy':chosen,
        'max_construction_calls_total':4,'max_construction_cost_usd':.48,'case_ids':ids,
        'execute':args.execute,'production_route':False,'gpu_rental':False})
    if not args.execute:print('Offline preview saved; no credentials or network.');return
    ledger=UsageLedger();key=MacKeychain(account=b'openai-api-key').load()
    if not key:raise CommandError('Saved research connection missing')
    execute(items,args.output,ledger,key,chosen)

if __name__=='__main__':main()
