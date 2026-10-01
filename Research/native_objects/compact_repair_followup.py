"""One previously undispatched repair, with lossless input feedback tables only."""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
from Research.native_objects import repair_experiment as original
from Research.native_objects import feedback_transport as codec

prior=original.prior
ROOT=original.ROOT
CASE='generic-drone'
OP=CASE+'/patch/1'
PARENT_CHARGE=187_987_500
BATCH=original.previous.transport.Batch('repair-013',(OP,),120_000_000,4_200_000_000+PARENT_CHARGE,5_000_000_000)


def prepare(source):
    protocol=original._read(source,'protocol.json')
    if protocol['experiment']!='repair-012':raise prior.CommandError('Unexpected parent experiment')
    for name,digest in protocol['files_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise prior.CommandError('Parent frozen code changed')
    result=original._read(source,'result.json');state=deepcopy(next(s for s in result['cases'] if s['case']==CASE))
    if result['operations'][OP]['status']!='halted' or state['status']!='geometry_failed':raise prior.CommandError('Expected undispatched failed candidate')
    baseline=source/(CASE+'-plan-0');raw=original._read(baseline,'compact-plan.json');report=original._read(baseline,'relations.json')
    scope=original.local.scope(raw,report);context=original.context_for(state)
    context.update(previous_compact_plan=raw,application_feedback=original.previous.repair.feedback(report,original._read(baseline,'repair-baseline.json')),
        locked_assembly=original._read(baseline,'assembly-lock.json'),locked_arrangement_bindings=original._read(baseline,'arrangement-bindings.json'))
    policy,body=original.body_for('patch',context,raw,scope)
    saved=original._read(source/(CASE+'-patch-call-1'),'request.json')['body'];saved=deepcopy(saved);saved.pop('background');saved.pop('metadata')
    if saved!=body or prior.digest(body)!=result['operations'][OP]['body_sha256']:raise prior.CommandError('Parent blocked request changed')
    content=json.loads(body['input'][1]['content']);before=deepcopy(content);feedback=content['application_feedback'];encoded=codec.encode(feedback)
    content['application_feedback']=encoded;restored=deepcopy(content);restored['application_feedback']=codec.decode(encoded)
    if restored!=before:raise prior.CommandError('Compaction changed context')
    body['input'][0]['content']+=codec.INSTRUCTIONS;body['input'][1]['content']=json.dumps(content,separators=(',',':'))
    return state,baseline,raw,scope,policy,body,codec.audit(feedback,encoded)


def source_hashes(source):
    files=[Path(__file__),original.SOURCE/'feedback_transport.py',original.SOURCE/'COMPACT_REPAIR_FOLLOWUP.md',source/'protocol.json',source/'result.json',
        source/(CASE+'-patch-call-1/request.json')]
    files.extend((source/(CASE+'-plan-0')).glob('*.json'))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def run(source,output,ledger,key,protocol):
    state,baseline,raw,scope,policy,body,audit=prepare(source)
    if source_hashes(source)!=protocol['files_sha256']:raise prior.CommandError('Frozen compact continuation changed')
    if ledger.get(original.BATCH.operation_id(OP)) or original.BATCH.spent(ledger)!=PARENT_CHARGE:raise prior.CommandError('Parent repair already reserved or parent spending changed')
    if PARENT_CHARGE+BATCH.budget>original.BATCH.budget:raise prior.CommandError('Combined authorized comparison allowance exceeded')
    prior.write(output/'transport-audit.json',audit);status='prepared';error=None
    try:
        patch,billing=original.background.dispatch(BATCH.operation_id(OP),policy,body,output/(CASE+'-patch-call-1'),ledger,key,BATCH)
        folder=output/(CASE+'-plan-1');folder.mkdir(exist_ok=True)
        prior.write(folder/'patch.json',patch);prior.write(folder/'repair-scope.json',scope)
        state['trace'].append({'stage':'compact_patch','attempt':1,'model_seconds':billing['dispatch_seconds'],
            'model_calls':billing['creation_calls'],'polls':billing['poll_calls'],'usage':billing['usage'],'calculated_cost_nanos':billing['calculated_cost_nanos']})
        revised,patch_audit=original.local.apply(raw,patch,scope,state['contract']);prior.write(folder/'patch-audit.json',patch_audit)
        state['trace'].append({'stage':'patch_admission',**patch_audit})
        if revised is None:state['status']='repair_unsupported'
        else:original.evaluate(revised,state,folder,1,baseline)
        status='completed'
    except original.background.Pending as exc:status='pending';error=str(exc)
    except prior.CommandError as exc:status='halted';error=str(exc)
    except (ValueError,KeyError,TypeError) as exc:status='rejected';error=str(exc);state['status']='patch_rejected'
    prior.write(output/'result.json',{'status':status,'error':error,'cases':[state],'parent_experiment':'repair-012','parent_attempts_replayed':True,'native_generation_goal_passed':False})
    prior.write(output/'assessment.json',original.previous.assess({CASE:state},output))
    prior.write(output/'spending.json',{'charged_and_held_nanos':BATCH.spent(ledger),'parent_charge_nanos':PARENT_CHARGE,
        'combined_nanos':BATCH.spent(ledger)+PARENT_CHARGE,'combined_ceiling_nanos':original.BATCH.budget,
        'daily_remaining_nanos':ledger.summary()['remaining_nanos'],'actual_invoiced_cost':None})
    prior.write(output/'index.json',[{'name':p.name} for p in sorted(output.iterdir()) if p.is_dir() and (p/'package.json').exists()])
    (output/'index.html').write_text((original.SOURCE/'viewer.html').read_text())
    print(json.dumps({'status':status,'error':error,'case_status':state['status'],'combined_usd':(PARENT_CHARGE+BATCH.spent(ledger))/1e9}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--resume',action='store_true');args=p.parse_args()
    source=args.source.resolve();output=args.output.resolve()
    prepare(source)
    if args.resume:
        protocol=original._read(output,'protocol.json')
        if protocol['experiment']!=BATCH.experiment or protocol['files_sha256']!=source_hashes(source):raise prior.CommandError('Resume requires unchanged compact continuation')
    else:
        output.mkdir(parents=True,exist_ok=False)
        protocol={'experiment':BATCH.experiment,'parent_experiment':'repair-012','files_sha256':source_hashes(source),
            'allowed_operations':BATCH.cases,'budget_nanos':BATCH.budget,'prior_upper_bound_nanos':BATCH.prior_upper_bound,
            'aggregate_limit_nanos':BATCH.aggregate_limit,'combined_ceiling_nanos':original.BATCH.budget,
            'policy':original.selected('patch'),'geometry_executor_changed':False,'new_initial_plan_allowed':False,'scope_changed':False}
        prior.write(output/'protocol.json',protocol)
    if args.execute:
        with open(ROOT/'.oryn-usage'/(BATCH.experiment+'.lock'),'a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);key=prior.MacKeychain(account=b'openai-api-key').load()
            if not key:raise prior.CommandError('Model connection unavailable')
            run(source,output,prior.UsageLedger(),key,protocol)

if __name__=='__main__':main()
