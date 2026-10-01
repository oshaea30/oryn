"""Funded continuation of 014; reuse its candidate and retain its failed-job hold."""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import time
from Research.native_objects import strong_model_experiment as previous

baseline=previous.baseline
prior=previous.prior
ROOT=previous.ROOT
SOURCE=previous.SOURCE
PARENT=ROOT/'Builds/NativeObjects/strong-model-run-014'
OPERATIONS=('generic-drone/patch/1','two-driver-speaker/extract/0','two-driver-speaker/plan/0','cooling-fan-row/patch/1')
BATCH=baseline.previous.transport.Batch('strong-model-015',OPERATIONS,7_500_000_000,7_400_000_000,15_000_000_000)
FAILED=PARENT/'generic-drone-patch-call-1'
REPLAY_DIRS=('generic-drone-extract','generic-drone-plan-0','cooling-fan-row-extract','cooling-fan-row-plan-0')


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_parent():
    protocol=read(PARENT/'protocol.json')
    for name,digest in protocol['files_sha256'].items():
        if name=='Research/native_objects/strong_model_experiment.py':continue  # Only runner parameterization changes.
        if sha(ROOT/name)!=digest:raise prior.CommandError('Parent comparison inputs or executor changed')
    saved=read(SOURCE/'results/strong-model-014/request-response-package-hashes.json')
    for name,digest in saved.items():
        if sha(PARENT/name)!=digest:raise prior.CommandError('Parent request/response/package changed')
    if sha(PARENT/'result.json')!=sha(SOURCE/'results/strong-model-014/result.json'):raise prior.CommandError('Parent state changed')


def frozen_sources():
    hashes=previous.frozen_sources()
    paths=[Path(__file__),SOURCE/'STRONG_MODEL_CONTINUATION.md',PARENT/'protocol.json',PARENT/'result.json']
    paths+=list(FAILED.glob('*.json'))
    for name in REPLAY_DIRS:paths+=list((PARENT/name).glob('*.json'))
    for path in paths:hashes[str(path.relative_to(ROOT))]=sha(path)
    return hashes


def prepare(output):
    verify_parent();states={s['case']:s for s in read(PARENT/'result.json')['cases']}
    expected={'generic-drone':'geometry_failed','cooling-fan-row':'geometry_failed','two-driver-speaker':'needs_requirements'}
    if {c:s['status'] for c,s in states.items()}!=expected:raise prior.CommandError('Unexpected parent continuation state')
    for name in REPLAY_DIRS:shutil.copytree(PARENT/name,output/name)
    prior.write(output/'result.json',{'cases':list(states.values()),'native_generation_goal_passed':False})
    prior.write(output/'replay-audit.json',{'source_experiment':'strong-model-014','model_calls':0,'new_cost_nanos':0,
        'files_sha256':{str(p.relative_to(PARENT)):sha(p) for n in REPLAY_DIRS for p in (PARENT/n).iterdir() if p.is_file()},
        'detail':'All copied packages/plans are unchanged; existing traces remain historical, not new 015 calls.'})
    return states


def funding_evidence(folder=FAILED,expected_response_hash=None):
    request=read(folder/'request.json');job=read(folder/'job.json');response=read(folder/'response.json')
    expected_response_hash=expected_response_hash or read(SOURCE/'results/strong-model-014/request-response-package-hashes.json')['generic-drone-patch-call-1/response.json']
    if sha(folder/'response.json')!=expected_response_hash:raise prior.CommandError('Funding evidence hash changed')
    body=request['body']
    valid=(response.get('status')=='failed' and response.get('error',{}).get('code')=='credit_balance_exhausted'
        and response.get('usage') is None and response.get('output')==[] and response.get('model')==body['model']=='gpt-6-astra'
        and response.get('service_tier')=='default' and job['status']=='failed' and job['response_id']==response['id']
        and job['creation_calls']==1 and job['cancel_calls']==0 and body.get('metadata',{}).get('oryn_operation')==job['operation_id']
        and request['body_sha256']==job['body_sha256']==prior.digest(body))
    if not valid:raise prior.CommandError('Only the reviewed terminal funding failure permits this recovery')
    return {'operation_id':job['operation_id'],'response_id':response['id'],'response_sha256':expected_response_hash,
        'body_sha256':job['body_sha256'],'error_code':response['error']['code'],'user_confirmed_reload':True}


def restore_admission(ledger,audit_path,evidence):
    """Explicit operator review: retain charge/uncertainty, only reopen a reviewed stop."""
    ident=evidence['operation_id'];existing=read(audit_path) if audit_path.exists() else None
    with ledger.transaction() as db:
        control=dict(db.execute('SELECT * FROM control WHERE id=1').fetchone())
        row=dict(db.execute('SELECT * FROM usage WHERE request_id=?',(ident,)).fetchone() or {})
        if not row or row['status']!='uncertain' or row['outcome']!='usage_unconfirmed' or row['fingerprint']!=evidence['body_sha256'] or row['charged_nanos']!=row['reserved_nanos'] or row['calculated_cost_nanos'] is not None or row['actual_cost_nanos'] is not None or row['model']!='gpt-6-astra' or row['profile']!='research_astra_xhigh':
            raise prior.CommandError('Funding hold changed; accounting requires review')
        if int(ledger.clock())<control['last_clock']:raise prior.CommandError('Clock moved backward; recovery rejected')
        if existing:
            if existing['evidence']!=evidence or existing['ledger_row_before']!=row:raise prior.CommandError('Recovery audit no longer matches the held request')
            if not control['halted']:
                existing['status']='completed';baseline.background.save(audit_path,existing);return existing
            if existing['status']=='completed':raise prior.CommandError('Ledger halted again after recovery; inspect new failure')
        elif not control['halted']:raise prior.CommandError('Funding recovery expects the recorded ledger halt')
        # Do not clear a halt when another operation could have caused it.
        later=db.execute('SELECT request_id FROM usage WHERE request_id!=? AND (created>? OR finished>? OR status=?)',
            (ident,row['created'],row['finished'],'reserved')).fetchall()
        if later:raise prior.CommandError('Later or active requests require separate recovery review')
        audit={'status':'prepared','evidence':evidence,'ledger_row_before':row,'control_before':control,
            'reviewed_at':int(ledger.clock()),'hold_retained_nanos':row['charged_nanos'],'billing_reconciled':False,'released_nanos':0}
        baseline.background.save(audit_path,audit)
        db.execute('UPDATE control SET halted=0 WHERE id=1')
    audit['status']='completed';baseline.background.save(audit_path,audit);return audit


def remaining_bodies(output,states):
    for op in (OPERATIONS[0],OPERATIONS[1],OPERATIONS[-1]):
        case,stage,_=op.split('/');raw=scope=None
        if stage=='patch':context,raw,scope=previous.patch_context(states[case],output/(case+'-plan-0'))
        else:
            spec=next(s for s in baseline.SPECS if s['id']==case);context={'original_request':spec['request'],'proposed_role_groups':spec['roles']}
        p,body,_=previous.body_for(stage,context,raw,scope,compact_feedback=case=='generic-drone')
        if case=='generic-drone':
            old=deepcopy(read(FAILED/'request.json')['body']);old.pop('background');old.pop('metadata')
            if body!=old:raise prior.CommandError('Prepared drone repair request changed')
            comparison={'input_identical':True,'output_schema_identical':True,'source':'014 funding-failed request'}
        else:comparison=previous.comparison_audit(op,body)
        yield op,p,body,comparison


def preflight(output,states,key,ledger,allow_reviewed_halt=False):
    rows=[]
    for op,p,body,comparison in remaining_bodies(output,states):
        count=prior.count_input(key,body);rows.append({'operation':op,'input_tokens':count,'maximum_nanos':prior.quote_cost(p,count),'comparison':comparison})
    conditional=prior.quote_cost(previous.selected(),32768);worst=sum(r['maximum_nanos'] for r in rows)+conditional;summary=ledger.summary()
    parent_spent=previous.BATCH.spent(ledger)
    if BATCH.spent(ledger) or parent_spent!=2_921_787_500 or worst>BATCH.budget or worst+BATCH.prior_upper_bound>BATCH.aggregate_limit or worst>summary['remaining_nanos'] or summary['halted'] and not allow_reviewed_halt:
        raise prior.CommandError('Whole funded continuation cannot fit reviewed allowance')
    audit={'fixed_operations':rows,'conditional_worst_case_nanos':conditional,'whole_batch_maximum_nanos':worst,
        'continuation_ceiling_nanos':BATCH.budget,'prior_including_holds_nanos':BATCH.prior_upper_bound,'aggregate_ceiling_nanos':BATCH.aggregate_limit,
        'parent_charged_and_held_nanos':parent_spent,'combined_comparison_worst_with_old_hold_nanos':parent_spent+worst,
        'daily_remaining_before_nanos':summary['remaining_nanos'],'generation_dispatched':False,'old_funding_hold_released':False}
    prior.write(output/'preflight.json',audit);return audit


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--funding-restored',action='store_true');p.add_argument('--resume',action='store_true');args=p.parse_args()
    if args.resume:
        protocol=read(args.output/'protocol.json');states={s['case']:s for s in read(args.output/'result.json')['cases']}
        if protocol['experiment']!=BATCH.experiment or frozen_sources()!=protocol['files_sha256']:raise prior.CommandError('Resume requires unchanged continuation')
    else:
        args.output.mkdir(parents=True,exist_ok=False);states=prepare(args.output)
        protocol={'experiment':BATCH.experiment,'parent_experiment':'strong-model-014','files_sha256':frozen_sources(),'policy':previous.selected(),
            'allowed_operations':OPERATIONS,'batch_ceiling_nanos':BATCH.budget,'prior_upper_bound_nanos':BATCH.prior_upper_bound,'aggregate_limit_nanos':BATCH.aggregate_limit,
            'job_deadline_seconds':900,'geometry_executor_changed':False,'acceptance_changed':False,'maximum_calls':4,'manual_repairs_allowed':False}
        prior.write(args.output/'protocol.json',protocol)
    if not args.execute:return
    with open(ROOT/'.oryn-usage/strong-model-014.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
        if not key:raise prior.CommandError('Model connection unavailable')
        if not (args.output/'preflight.json').exists():
            evidence=funding_evidence()
            audit=preflight(args.output,states,key,ledger,allow_reviewed_halt=args.funding_restored)
            print(json.dumps({'whole_continuation_maximum_usd':audit['whole_batch_maximum_nanos']/1e9,'generation_dispatched':False}),flush=True)
        if ledger.summary()['halted']:
            if not args.funding_restored:raise prior.CommandError('Operator must review the recorded funding stop after reload confirmation')
            restore_admission(ledger,args.output/'funding-review.json',funding_evidence())
        if ledger.summary()['halted']:raise prior.CommandError('Paid admission still halted')
        previous.run(args.output,states,protocol,ledger,key,batch=BATCH,operation_order=OPERATIONS,snapshot=frozen_sources)

if __name__=='__main__':main()
