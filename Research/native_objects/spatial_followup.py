"""Spatial 009: recompile only 008's completed-but-invalid typed translations."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
from Research.native_objects import spatial_experiment as previous

prior=previous.prior
pipeline=previous.pipeline
spatial=previous.spatial
CASES=('generic-drone','static-concept')
OPERATIONS=tuple(c+'/'+s+'/'+str(a) for c in CASES for s,n in [('extract',1),('plan',2)] for a in range(n))
BATCH=previous.transport.Batch('spatial-009',OPERATIONS,750_000_000,3_500_000_000,5_000_000_000)


def eligible(source):
    states=json.loads((source/'result.json').read_text())['cases'];lookup={s['case']:s for s in states}
    if any(s['status']=='extracting' or any(a['status']=='planning' for a in s.get('attempts',[])) for s in states):raise ValueError('Source batch is still active')
    for case in CASES:
        state=lookup[case];folder=source/(case+'-extract')
        if state['status']!='extraction_failed' or state['attempts'] or state['geometry_executed']:raise ValueError('Only rejected, never-planned translations are eligible')
        meta=json.loads((folder/'response-metadata.json').read_text())
        if meta['status']!='completed' or not (folder/'inventory.json').exists():raise ValueError('No retry of an incomplete or uncertain extraction')
    return lookup


def request(case,stage,attempt,context,folder,ledger,key):
    op=case+'/'+stage+'/'+str(attempt)
    if op not in BATCH.cases:raise prior.CommandError('Outside frozen spatial follow-up')
    p,body=previous.body_for(stage,context)
    return previous.transport.dispatch(BATCH.operation_id(op),p,body,folder,ledger,key,batch=BATCH,timeout=240 if stage=='plan' else 120)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    sources=eligible(args.source);args.output.mkdir(parents=True,exist_ok=False)
    files=[previous.SOURCE/n for n in ('spatial_requirements.py','spatial_experiment.py','spatial_followup.py','requirements_experiment.py',
        'requirement_meaning.py','intent_requirements.py','compact_construction.py','assembly_connections.py','construction_solid.py',
        'construction.py','meaning_experiment.py','meaning_cases_005.json','results/planning-001.json','results/construction-001/heldout-plan.json')]+[previous.ROOT/'Orchestrator/spending.py']
    hashes={str(p.relative_to(previous.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    inputs=previous.items()
    for case in CASES:
        if next(i['request'] for i in inputs if i['case_id']==case)!=sources[case]['request']:raise ValueError('Original request changed')
    prior.write(args.output/'protocol.json',{'experiment':BATCH.experiment,'cases':CASES,'source':str(args.source),
        'source_result_sha256':hashlib.sha256((args.source/'result.json').read_bytes()).hexdigest(),
        'prior_failures':{c:sources[c]['error'] for c in CASES},'budget_nanos':BATCH.budget,
        'prior_upper_bound_nanos':BATCH.prior_upper_bound,'aggregate_limit_nanos':BATCH.aggregate_limit,
        'files_sha256':hashes,'policies':{s:previous.selected(s) for s in ('extract','plan')},
        'request_deadlines_seconds':{'extract':120,'plan':240},'spatial_policy':spatial.POLICY,'execute':args.execute})
    if not args.execute:return
    lock=open(previous.ROOT/'.oryn-usage'/(BATCH.experiment+'.lock'),'a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
    if not key:raise prior.CommandError('Model connection unavailable')
    stopped=[]
    def model(case,stage,attempt,context,folder):
        if stopped:raise prior.CommandError('Batch stopped: '+stopped[0])
        if any(hashlib.sha256((previous.ROOT/n).read_bytes()).hexdigest()!=h for n,h in hashes.items()):raise prior.CommandError('Frozen follow-up changed')
        try:return request(case,stage,attempt,context,folder,ledger,key)
        except prior.CommandError as error:stopped.append(str(error));raise
    states=pipeline.execute(inputs,args.output,model,case_ids=CASES)
    prior.write(args.output/'assessment.json',previous.assess(states));summary=ledger.summary()
    prior.write(args.output/'spending.json',{'charged_and_held_nanos':BATCH.spent(ledger),'daily_remaining_nanos':summary['remaining_nanos'],'stopped':stopped,'actual_invoiced_cost':None})
    print(json.dumps({'charged_and_held_usd':BATCH.spent(ledger)/1e9,'daily_remaining_usd':summary['remaining_nanos']/1e9,
        'cases':[{k:s[k] for k in ('case','status','geometry_executed')} for s in states.values()]}))

if __name__=='__main__':main()
