"""Small application-owned planning batch. Preview is offline; execute calls one model/case."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Orchestrator'))
from cognition import CommandError
from credential_store import MacKeychain, CredentialError
from object_planning import build_request, planning_body, OpenAIObjectPlanner, INSTRUCTIONS, SCHEMA
from spending import policy, digest
from usage_ledger import UsageLedger


def write(path,value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def prepare(protocol):
    if not isinstance(protocol,dict) or protocol.get('max_calls')!=4 or protocol.get('max_cost_usd')!=0.20:
        raise ValueError('Expected the bounded four-case protocol.')
    cases=protocol.get('cases')
    if not isinstance(cases,list) or len(cases)!=4 or len({c['id'] for c in cases})!=4:
        raise ValueError('Four unique cases required.')
    chosen=policy('openai','planning',int(time.time()))
    if chosen['ceiling_nanos']*len(cases)>200_000_000:raise ValueError('Batch exceeds 20-cent ceiling.')
    items=[]
    for c in cases:
        request=build_request(c['request'],c['sources'])
        body=planning_body(chosen,request)
        items.append({'case_id':c['id'],'operation_id':digest({'protocol':protocol['id'],'body':body})[:32],
                      'request':request,'body':body,'status':'not_started'})
    return {'protocol':protocol,'protocol_sha256':digest(protocol),'instructions_sha256':digest(INSTRUCTIONS),
            'schema_sha256':digest(SCHEMA),'profile':chosen,'items':items,'execution_requested':False,
            'geometry_generated':False,'semantic_assessment':'not_assessed'}


def execute(record,provider,ledger,output):
    for item in record['items']:
        item['status']='running';item['started_at']=time.time();record['execution_requested']=True
        write(output/'run.json',record)
        print('Planning '+item['case_id'],flush=True)
        context=item['request']['context']
        try:
            candidate=provider.plan(item['operation_id'],context['request'],context['sources'],
                current_context=lambda:(context['request'],context['sources']))
            item.update(status='completed',candidate=candidate)
        except CommandError as error:
            item.update(status='failed',error=str(error))
        item['elapsed_seconds']=round(time.time()-item['started_at'],3)
        row=ledger.get(item['operation_id'])
        item['billing']=({k:row[k] for k in ('status','outcome','reserved_nanos','calculated_cost_nanos','actual_cost_nanos',
                                           'actual_input_tokens','actual_output_tokens')} if row else None)
        write(output/'run.json',record)
        if ledger.summary()['halted']:break
    record['status']='completed' if all(i['status']=='completed' for i in record['items']) else 'incomplete'
    record['charged_or_reserved_nanos']=sum((i.get('billing') or {}).get('calculated_cost_nanos') or
        ((i.get('billing') or {}).get('reserved_nanos',0) if (i.get('billing') or {}).get('status') in ('uncertain','reserved') else 0)
        for i in record['items'])
    write(output/'run.json',record)
    print(json.dumps({'status':record['status'],'charged_or_reserved_nanos':record['charged_or_reserved_nanos'],
                      'geometry_generated':False,'semantic_assessment':'not_assessed'}))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',type=Path,default=Path(__file__).with_name('planning_cases_001.json'))
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--execute',action='store_true',help='Use saved ORYN research key; four calls maximum, 20-cent ceiling shared with daily ledger')
    args=p.parse_args()
    try:
        record=prepare(json.loads(args.cases.read_text()))
        args.output.mkdir(parents=True,exist_ok=False)
        write(args.output/'run.json',record)
        if not args.execute:
            print('Offline preview saved. No credentials loaded, model call, retrieval or generation.');return
        try:
            ledger=UsageLedger();key=MacKeychain(account=b'openai-api-key').load()
            if not key:raise CommandError('Saved ORYN research connection missing.')
        except (CommandError,CredentialError):
            record.update(status='blocked',error='Saved research connection or usage ledger unavailable.')
            write(args.output/'run.json',record)
            raise CommandError(record['error']) from None
        execute(record,OpenAIObjectPlanner(ledger,key),ledger,args.output)
    except (CommandError,CredentialError,ValueError,OSError) as error:p.error(str(error))

if __name__=='__main__':main()
