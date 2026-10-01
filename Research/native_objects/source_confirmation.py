"""Meaning 006: one source-bound confirmation per response, with frozen assertions."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import time
from Research.native_objects import meaning_experiment as previous

prior=previous.prior
meaning=previous.meaning
SOURCE_DIR=Path(__file__).parent
BATCH=previous.Batch('meaning-006',('contrast_motion','original_drone','static_controller'),
                     150_000_000,2_800_000_000,5_000_000_000)
CASES=tuple(c for c in previous.CASES if c['id'] in BATCH.cases)


def request(case,folder,ledger,key):
    if case not in CASES:raise prior.CommandError('Case outside frozen confirmation')
    p=previous.selected()
    content={'request':case['request'],'proposed_role_groups':case['roles'],
             'source_units':meaning.source_units(case['request'])}
    body=prior.body(p,meaning.SOURCE_INSTRUCTIONS,json.dumps(content),
                    meaning.source_schema(case['request']),'oryn_source_bound_interpretation')
    return previous.dispatch(BATCH.operation_id(case['id']),p,body,folder,ledger,key,batch=BATCH)


def execute(output,model):
    records=[]
    for case in CASES:
        folder=output/case['id'];folder.mkdir()
        record={'case':case['id'],'geometry_executed':False};records.append(record)
        print('Confirm '+case['id'],flush=True);started=time.perf_counter();stop=False
        try:
            raw,bill=model(case,folder);prior.write(folder/'inventory.json',raw)
            contract=meaning.validate_source_output(raw,case['request'],case['roles'])
            prior.write(folder/'contract.json',contract)
            admission=meaning.preflight(contract);prior.write(folder/'admission.json',admission)
            assessment=previous.assess(case,contract,admission);prior.write(folder/'assessment.json',assessment)
            record.update(status='interpreted',planning_allowed=admission['planning_allowed'],
                predeclared_checks_passed=assessment['predeclared_checks_passed'],blocking=admission['blocking'])
        except prior.CommandError as error:
            record.update(status='stopped',error=str(error));stop=True
        except (ValueError,KeyError,TypeError) as error:
            record.update(status='stopped',error=str(error))
        finally:
            meta=folder/'response-metadata.json'
            if meta.exists():record['billing']=json.loads(meta.read_text())
            record['elapsed_seconds']=time.perf_counter()-started
            prior.write(output/'result.json',{'experiment':BATCH.experiment,'cases':records,
                'native_generation_goal_passed':False,'geometry_executed':False})
        if stop:break  # No automatic retry or further spend after a transport/billing stop.
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    frozen=[SOURCE_DIR/n for n in ('assembly_connections.py','construction_solid.py','construction.py',
            'requirement_meaning.py','meaning_cases_005.json','intent_requirements.py',
            'meaning_experiment.py','source_confirmation.py')]+[prior.ROOT/'Orchestrator/spending.py']
    hashes={str(p.relative_to(prior.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen}
    prior.write(args.output/'protocol.json',{'experiment':BATCH.experiment,'budget_nanos':BATCH.budget,
        'prior_upper_bound_nanos':BATCH.prior_upper_bound,'aggregate_limit_nanos':BATCH.aggregate_limit,
        'policy':previous.selected(),'files_sha256':hashes,'cases':CASES,
        'instructions_sha256':prior.digest(meaning.SOURCE_INSTRUCTIONS),
        'schemas_sha256':{c['id']:prior.digest(meaning.source_schema(c['request'])) for c in CASES},
        'execute':args.execute,'geometry_executed':False})
    if not args.execute:return
    lock=open(prior.ROOT/'.oryn-usage'/(BATCH.experiment+'.lock'),'a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
    if not key:raise prior.CommandError('Model connection unavailable')
    def model(case,folder):
        if any(hashlib.sha256((prior.ROOT/n).read_bytes()).hexdigest()!=h for n,h in hashes.items()):
            raise prior.CommandError('Frozen confirmation changed')
        return request(case,folder,ledger,key)
    execute(args.output,model)
    summary=ledger.summary()
    print(json.dumps({'charged_and_held_usd':BATCH.spent(ledger)/1e9,
        'shared_daily_limit_usd':summary['daily_limit_nanos']/1e9,
        'shared_daily_remaining_usd':summary['remaining_nanos']/1e9}))


if __name__=='__main__':main()
