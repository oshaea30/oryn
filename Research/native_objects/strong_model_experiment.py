"""One higher-capacity comparison using unchanged requests, tools and acceptance gates."""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import time
from Research.native_objects import repair_experiment as baseline
from Research.native_objects import feedback_transport as codec

prior=baseline.prior
ROOT=baseline.ROOT
SOURCE=baseline.SOURCE
OPERATIONS=('generic-drone/plan/0','generic-drone/patch/1','two-driver-speaker/extract/0','two-driver-speaker/plan/0','cooling-fan-row/patch/1')
BATCH=baseline.previous.transport.Batch('strong-model-014',OPERATIONS,10_000_000_000,4_470_000_000,15_000_000_000)
REFERENCES={'generic-drone/plan/0':'generic-drone-plan-call-0','two-driver-speaker/extract/0':'two-driver-speaker-extract-call-0','cooling-fan-row/patch/1':'cooling-fan-row-patch-call-1'}
CONTROL=ROOT/'Builds/NativeObjects/repair-run-012'


def selected():return prior.policy('openai','research_astra_xhigh',int(time.time()))


def body_for(stage,context,raw=None,scope=None,compact_feedback=False):
    _,body=baseline.body_for(stage,context,raw,scope);p=selected()
    body.update(model=p['model'],max_output_tokens=p['max_output_tokens'],reasoning={'effort':p['effort']})
    audit=None
    if compact_feedback:
        content=json.loads(body['input'][1]['content']);feedback=content['application_feedback'];content['application_feedback']=codec.encode(feedback)
        audit=codec.audit(feedback,content['application_feedback'])
        body['input'][0]['content']+=codec.INSTRUCTIONS;body['input'][1]['content']=json.dumps(content,separators=(',',':'))
    return p,body,audit


def patch_context(state,folder):
    raw=baseline._read(folder,'compact-plan.json');report=baseline._read(folder,'relations.json');scope=baseline.local.scope(raw,report)
    context=baseline.context_for(state)
    context.update(previous_compact_plan=raw,application_feedback=baseline.previous.repair.feedback(report,baseline._read(folder,'repair-baseline.json')),
        locked_assembly=baseline._read(folder,'assembly-lock.json'),locked_arrangement_bindings=baseline._read(folder,'arrangement-bindings.json'))
    return context,raw,scope


def comparison_audit(op,body):
    request=CONTROL/REFERENCES[op]/'request.json'
    saved_hashes=baseline._read(SOURCE/'results/repair-012','request-response-package-hashes.json')
    relative=str(request.relative_to(CONTROL))
    if hashlib.sha256(request.read_bytes()).hexdigest()!=saved_hashes[relative]:raise prior.CommandError('Historical request changed')
    old=baseline._read(request.parent,'request.json')['body'];old=deepcopy(old);old.pop('background');old.pop('metadata')
    audit=capacity_audit(old,body)
    return {'source':str(request.relative_to(ROOT)),**audit}


def capacity_audit(old,body):
    changed=[key for key in old if old[key]!=body.get(key)]
    if set(old)!=set(body) or set(changed)!={'model','reasoning','max_output_tokens'}:raise prior.CommandError('Comparison changed more than capacity controls')
    return {'old_body_sha256':prior.digest(old),'new_body_sha256':prior.digest(body),
        'changed_fields':changed,'input_identical':old['input']==body['input'],'output_schema_identical':old['text']==body['text'],
        'interpretation':'combined model/effort/output allowance comparison, not isolated model-only causality'}



def frozen_sources():
    hashes=baseline.frozen_sources()
    for path in (Path(__file__),SOURCE/'feedback_transport.py',SOURCE/'STRONG_MODEL_EXPERIMENT.md'):
        hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    for name in REFERENCES.values():
        path=CONTROL/name/'request.json';hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def preflight(output,states,key,ledger):
    rows=[]
    for op in REFERENCES:
        case,stage,num=op.split('/');state=states[case];raw=scope=None
        if stage=='patch':context,raw,scope=patch_context(state,output/(case+'-plan-0'))
        elif stage=='extract':
            spec=next(s for s in baseline.SPECS if s['id']==case);context={'original_request':spec['request'],'proposed_role_groups':spec['roles']}
        else:context=baseline.context_for(state)
        p,body,_=body_for(stage,context,raw,scope);audit=comparison_audit(op,body)
        count=prior.count_input(key,body);maximum=prior.quote_cost(p,count)
        rows.append({'operation':op,'input_tokens':count,'maximum_nanos':maximum,'comparison':audit})
    # Cover BOTH not-yet-known conditional inputs at the full reviewed context limit.
    conditional=2*prior.quote_cost(selected(),32768)
    worst=sum(r['maximum_nanos'] for r in rows)+conditional
    summary=ledger.summary()
    if worst>BATCH.budget or BATCH.prior_upper_bound+worst>BATCH.aggregate_limit or worst>summary['remaining_nanos'] or summary['halted']:
        raise prior.CommandError('Whole comparison cannot fit authorized allowance before dispatch')
    result={'fixed_operations':rows,'conditional_worst_case_nanos':conditional,'whole_batch_maximum_nanos':worst,
        'daily_limit_nanos':summary['daily_limit_nanos'],'daily_remaining_before_nanos':summary['remaining_nanos'],
        'generation_dispatched':False,'model':selected()['model'],'effort':selected()['effort'],'max_output_tokens':32768}
    prior.write(output/'preflight.json',result);return result


def run(output,states,protocol,ledger,key,*,batch=BATCH,operation_order=OPERATIONS,snapshot=frozen_sources):
    operations=baseline._read(output,'operations.json') if (output/'operations.json').exists() else {};stopped=[]
    def persist():
        prior.write(output/'operations.json',operations)
        prior.write(output/'result.json',{'cases':list(states.values()),'operations':operations,'native_generation_goal_passed':False})
    for op in operation_order:
        if operations.get(op,{}).get('status') in ('done','skipped','rejected'):continue
        case,stage,num=op.split('/');attempt=int(num);state=states[case]
        if stage=='plan' and state['status']!='requirements_ready' or stage=='patch' and state['status']!='geometry_failed':
            operations[op]={'status':'skipped','reason':state['status']};persist();continue
        record=operations.setdefault(op,{'status':'prepared','case':case,'stage':stage,'attempt':attempt})
        try:
            raw=scope=None
            if stage=='patch':context,raw,scope=patch_context(state,output/(case+'-plan-0'))
            elif stage=='extract':
                spec=next(s for s in baseline.SPECS if s['id']==case);context={'original_request':spec['request'],'proposed_role_groups':spec['roles']}
            else:context=baseline.context_for(state)
            p,body,transport_audit=body_for(stage,context,raw,scope,compact_feedback=op=='generic-drone/patch/1')
            if snapshot()!=protocol['files_sha256']:raise prior.CommandError('Frozen stronger-model experiment changed')
            if op in REFERENCES:record['comparison']=comparison_audit(op,body)
            callfolder=output/(case+'-'+stage+'-call-'+num);callfolder.mkdir(exist_ok=True)
            if transport_audit:prior.write(callfolder/'transport-audit.json',transport_audit)
            record.update(status='waiting',body_sha256=prior.digest(body));persist()
            print('Running '+op+' with Astra xhigh',flush=True)
            result,bill=baseline.background.dispatch(batch.operation_id(op),p,body,callfolder,ledger,key,batch,wait_seconds=900)
            prior.write(callfolder/'model-output.json',result);record.update(status='model_completed',billing=bill);persist()
            state['trace'].append({'stage':stage,'attempt':attempt,'model_seconds':bill['dispatch_seconds'],'usage':bill['usage'],
                'model':p['model'],'effort':p['effort'],'calculated_cost_nanos':bill['calculated_cost_nanos']})
            if stage=='extract':
                folder=output/(case+'-extract');folder.mkdir(exist_ok=True);prior.write(folder/'compact-inventory.json',result)
                full=baseline.typed.decode(result);prior.write(folder/'inventory.json',full)
                contract=baseline.arrangements.validate(full,spec['request'],spec['roles']);admission=baseline.arrangements.preflight(contract)
                prior.write(folder/'contract.json',contract);prior.write(folder/'admission.json',admission)
                state.update(contract=contract,admission=admission,status='requirements_ready' if admission['planning_allowed'] else 'unsupported_before_planning')
            elif stage=='plan':baseline.evaluate(result,state,output/(case+'-plan-0'),0)
            else:
                folder=output/(case+'-plan-1');folder.mkdir(exist_ok=True);prior.write(folder/'patch.json',result);prior.write(folder/'repair-scope.json',scope)
                revised,audit=baseline.local.apply(raw,result,scope,state['contract']);prior.write(folder/'patch-audit.json',audit)
                state['trace'].append({'stage':'patch_admission',**audit})
                if revised is None:state['status']='repair_unsupported'
                else:baseline.evaluate(revised,state,folder,1,output/(case+'-plan-0'))
            record['status']='done';persist();print(case+': '+state['status'],flush=True)
        except baseline.background.Pending as error:record.update(status='pending',error=str(error));stopped.append('retrieval_pending');persist();break
        except prior.CommandError as error:record.update(status='halted',error=str(error));stopped.append(str(error));persist();break
        except (ValueError,KeyError,TypeError) as error:
            record.update(status='rejected',error=str(error));state.update(status=stage+'_rejected',error=str(error));persist()
    prior.write(output/'assessment.json',baseline.previous.assess(states,output))
    summary=ledger.summary();prior.write(output/'spending.json',{'charged_and_held_nanos':batch.spent(ledger),'batch_ceiling_nanos':batch.budget,
        'prior_upper_bound_nanos':batch.prior_upper_bound,'aggregate_limit_nanos':batch.aggregate_limit,
        'daily_limit_nanos':summary['daily_limit_nanos'],'daily_remaining_nanos':summary['remaining_nanos'],'stopped':stopped,'actual_invoiced_cost':None})
    prior.write(output/'index.json',[{'name':p.name} for p in sorted(output.iterdir()) if p.is_dir() and (p/'package.json').exists()])
    (output/'index.html').write_text((SOURCE/'viewer.html').read_text());persist()
    print(json.dumps({'status':stopped or 'finished','charged_and_held_usd':batch.spent(ledger)/1e9,
        'cases':[{k:s[k] for k in ('case','status','geometry_executed')} for s in states.values()]}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--preflight',action='store_true');p.add_argument('--resume',action='store_true');args=p.parse_args()
    if args.resume:
        protocol=baseline._read(args.output,'protocol.json');states={s['case']:s for s in baseline._read(args.output,'result.json')['cases']}
        if protocol['experiment']!=BATCH.experiment or frozen_sources()!=protocol['files_sha256']:raise prior.CommandError('Resume requires unchanged stronger-model comparison')
    else:
        args.output.mkdir(parents=True,exist_ok=False);states=baseline.initialize(args.output)
        protocol={'experiment':BATCH.experiment,'files_sha256':frozen_sources(),'policy':selected(),'allowed_operations':OPERATIONS,
            'batch_ceiling_nanos':BATCH.budget,'prior_upper_bound_nanos':BATCH.prior_upper_bound,'aggregate_limit_nanos':BATCH.aggregate_limit,
            'job_deadline_seconds':900,'geometry_executor_changed':False,'acceptance_changed':False,'maximum_calls':5,'manual_repairs_allowed':False}
        prior.write(args.output/'protocol.json',protocol);prior.write(args.output/'result.json',{'cases':list(states.values()),'native_generation_goal_passed':False})
    if not args.execute and not args.preflight:return
    with open(ROOT/'.oryn-usage'/(BATCH.experiment+'.lock'),'a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
        if not key:raise prior.CommandError('Model connection unavailable')
        if not args.resume or not (args.output/'preflight.json').exists():
            audit=preflight(args.output,states,key,ledger);print(json.dumps({'whole_batch_maximum_usd':audit['whole_batch_maximum_nanos']/1e9,'generation_dispatched':False}),flush=True)
        if args.execute:run(args.output,states,protocol,ledger,key)

if __name__=='__main__':main()
