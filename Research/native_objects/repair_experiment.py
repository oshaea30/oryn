"""Assembly 012: recoverable planning and bounded edits with unchanged geometry."""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import time
from Research.native_objects import assembly_followup as previous
from Research.native_objects import background_requests as background
from Research.native_objects import typed_requirements as typed
from Research.native_objects import local_repair as local

prior=previous.prior
pipeline=previous.pipeline
arrangements=previous.arrangements
ROOT=previous.ROOT
SOURCE=previous.SOURCE
CASES=previous.CASES
SPECS=previous.SPECS
OPERATIONS=('cooling-fan-row/patch/1','two-driver-speaker/extract/0','generic-drone/plan/0',
            'two-driver-speaker/plan/0','generic-drone/patch/1','two-driver-speaker/patch/1')
BATCH=previous.transport.Batch('repair-012',OPERATIONS,780_000_000,4_200_000_000,5_000_000_000)


def selected(stage):
    p=previous.selected('extract' if stage=='extract' else 'plan');p['profile']='recoverable_research_'+stage
    if stage=='patch':p.update(max_output_tokens=6144,ceiling_nanos=120_000_000)
    return p


def body_for(stage,context,raw=None,scope=None):
    p=selected(stage)
    if stage=='extract':
        request=context['original_request'];roles=context['proposed_role_groups']
        content={'request':request,'entities':arrangements.spatial.meaning.entity_catalog(roles),'source_units':arrangements.spatial.meaning.source_units(request)}
        instructions=arrangements.EXTRACT_INSTRUCTIONS+typed.INSTRUCTIONS;schema=typed.schema(request,roles)
    else:
        content=pipeline.compact.planner_context(context)
        instructions=pipeline.compact.INSTRUCTIONS+arrangements.spatial.PLAN_INSTRUCTIONS+arrangements.PLAN_INSTRUCTIONS+previous.repair.INSTRUCTIONS+pipeline.compact.PLANNER_CONTEXT_INSTRUCTIONS
        if stage=='patch':
            instructions+=local.INSTRUCTIONS;schema=local.schema(raw,scope);content['repair_scope']=scope
        else:schema=pipeline.compact.SCHEMA
    return p,prior.body(p,instructions,json.dumps(content),schema,'oryn_recoverable_'+stage)


def context_for(state):
    c=state['contract']
    return {'original_request':state['request'],'requirements':c['inventory'],'requirement_hash':c['inventory_sha256'],
            'spatial_rules':c['spatial_rules'],'spatial_policy':pipeline.spatial.POLICY,
            'assemblies':c['assemblies'],'arrangement_policy':arrangements.POLICY}


def frozen_sources():
    names=('repair_experiment.py','background_requests.py','local_repair.py','typed_requirements.py','compact_requirements.py',
        'assembly_arrangements.py','arrangement_experiment.py','assembly_followup.py','arrangement_cases_010.json','spatial_requirements.py',
        'spatial_experiment.py','requirements_experiment.py','requirement_meaning.py','intent_requirements.py','compact_construction.py',
        'assembly_connections.py','construction_solid.py','construction.py','meaning_experiment.py','repair_feedback.py','LOCAL_REPAIR_EXPERIMENT.md')
    paths=[SOURCE/n for n in names]+[ROOT/'Orchestrator'/n for n in ('spending.py','usage_ledger.py')]
    for folder,files in [('results/assembly-010/cooling-fan-row-extract',('inventory.json','contract.json')),
                         ('results/assembly-010/cooling-fan-row-plan-0',('compact-plan.json','compiled.json','assembly-lock.json','arrangement-bindings.json')),
                         ('results/assembly-011/generic-drone-extract',('inventory.json','contract.json'))]:
        paths.extend(SOURCE/folder/f for f in files)
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def initialize(output):
    data=previous.prepare_replay();states={}
    for case in CASES:
        spec=next(c for c in SPECS if c['id']==case)
        states[case]={'case':case,'request':spec['request'],'status':'needs_requirements','attempts':[],'geometry_executed':False,'trace':[]}
        if case in ('generic-drone','cooling-fan-row'):
            source=SOURCE/('results/assembly-011' if case=='generic-drone' else 'results/assembly-010')/(case+'-extract')
            raw=json.loads((source/'inventory.json').read_text());contract=arrangements.validate(raw,spec['request'],spec['roles'])
            if contract!=json.loads((source/'contract.json').read_text()):raise ValueError('Saved interpretation changed')
            folder=output/(case+'-extract');folder.mkdir()
            for filename,value in (('inventory.json',raw),('contract.json',contract),('admission.json',arrangements.preflight(contract))):prior.write(folder/filename,value)
            states[case].update(status='requirements_ready',contract=contract,admission=arrangements.preflight(contract))
            states[case]['trace'].append({'stage':'requirements','replayed':True,'model_calls':0,'new_cost_nanos':0,'source':str(source.relative_to(ROOT))})
    folder=output/'cooling-fan-row-plan-0';folder.mkdir()
    prior.write(folder/'compact-plan.json',data['plan']);started=time.perf_counter()
    result,_=pipeline.evaluate_candidate(data['plan'],data['contract'],folder,'cooling-fan-row',preserve_passes=True)
    if json.loads((folder/'compiled.json').read_text())!=data['compiled']:raise ValueError('Fan solved baseline changed')
    states['cooling-fan-row'].update(status=result['status'],geometry_executed=True)
    states['cooling-fan-row']['attempts'].append({'attempt':0,**result,'replayed':True})
    states['cooling-fan-row']['trace'].append({'stage':'build_and_validate','replayed':True,'seconds':time.perf_counter()-started,'geometry_and_validation_seconds':result['geometry_and_validation_seconds'],'source_experiment':'assembly-010','source_attempt':0})
    return states


def _read(folder,name):return json.loads((folder/name).read_text())


def evaluate(raw,state,folder,attempt,baseline=None):
    folder.mkdir(exist_ok=True);prior.write(folder/'compact-plan.json',raw);before=time.perf_counter()
    kwargs={'preserve_passes':True}
    if baseline:
        kwargs.update(locked=(baseline/'assembly-lock.json').read_text(),locked_bindings=_read(baseline,'arrangement-bindings.json'),preservation=_read(baseline,'repair-baseline.json'))
    result,_=pipeline.evaluate_candidate(raw,state['contract'],folder,state['case'],**kwargs)
    state.update(status=result['status'],geometry_executed=state['geometry_executed'] or result['geometry_executed'])
    record={'attempt':attempt,**result};state['attempts'].append(record)
    stage={'stage':'build_and_validate','attempt':attempt,'seconds_including_render':time.perf_counter()-before,
        'geometry_executed':result['geometry_executed'],'geometry_and_validation_seconds':result.get('geometry_and_validation_seconds'),
        'full_assembly_validation':True,'planned_parts':len(raw['parts']),'planned_forms':sum(len(s['forms']) for s in raw['shapes'])}
    if (folder/'relations.json').exists():
        checks=_read(folder,'relations.json')['checks'];stage['validation_failures']=sum(not c['passed'] for c in checks)
        stage['failed_requirement_ids']=sorted({c['requirement_id'] for c in checks if not c['passed'] and 'requirement_id' in c})
    state['trace'].append(stage)
    return result


def run(output,ledger,key,protocol,states):
    started=time.perf_counter();operations=_read(output,'operations.json') if (output/'operations.json').exists() else {}
    def persist():
        prior.write(output/'operations.json',operations)
        prior.write(output/'result.json',{'cases':list(states.values()),'operations':operations,'native_generation_goal_passed':False})
    def call(case,stage,attempt,context,raw=None,scope=None):
        op=case+'/'+stage+'/'+str(attempt)
        if op not in OPERATIONS:raise prior.CommandError('Outside frozen repair experiment')
        folder=output/(case+'-'+stage+'-call-'+str(attempt));folder.mkdir(exist_ok=True)
        record=operations.setdefault(op,{'status':'prepared','stage':stage,'case':case,'attempt':attempt})
        p,body=body_for(stage,context,raw,scope)
        if any(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h for n,h in protocol['files_sha256'].items()):raise prior.CommandError('Frozen repair experiment changed')
        record.update(status='waiting',body_sha256=prior.digest(body));persist()
        result,billing=background.dispatch(BATCH.operation_id(op),p,body,folder,ledger,key,BATCH)
        prior.write(folder/'model-output.json',result);record.update(status='model_completed',billing=billing);persist()
        states[case]['trace'].append({'stage':stage,'attempt':attempt,'model_seconds':billing['dispatch_seconds'],
            'model_calls':billing['creation_calls'],'polls':billing['poll_calls'],'input_tokens':billing['usage']['input_tokens'],
            'output_tokens':billing['usage']['output_tokens'],'reasoning_tokens':billing['usage'].get('output_tokens_details',{}).get('reasoning_tokens'),
            'calculated_cost_nanos':billing['calculated_cost_nanos']})
        return result,record
    stopped=[]
    # Small held-baseline repair first; no repeated payment for its original plan.
    for op in OPERATIONS:
        case,stage,num=op.split('/');attempt=int(num);state=states[case]
        if operations.get(op,{}).get('status') in ('done','rejected','skipped'):continue
        if stage=='plan' and state['status']!='requirements_ready' or stage=='patch' and state['status']!='geometry_failed':
            operations[op]={'status':'skipped','reason':state['status']};persist();continue
        try:
            if stage=='extract':
                spec=next(s for s in SPECS if s['id']==case)
                raw,record=call(case,stage,attempt,{'original_request':spec['request'],'proposed_role_groups':spec['roles']})
                folder=output/(case+'-extract');folder.mkdir(exist_ok=True)
                prior.write(folder/'compact-inventory.json',raw);full=typed.decode(raw);prior.write(folder/'inventory.json',full)
                before=time.perf_counter();contract=arrangements.validate(full,spec['request'],spec['roles']);admission=arrangements.preflight(contract)
                prior.write(folder/'contract.json',contract);prior.write(folder/'admission.json',admission)
                state.update(contract=contract,admission=admission,status='requirements_ready' if admission['planning_allowed'] else 'unsupported_before_planning')
                state['trace'].append({'stage':'interpretation_validation','seconds':time.perf_counter()-before,'requirements':len(contract['inventory']['requirements']),'blocking_requirements':admission['blocking']})
            elif stage=='plan':
                raw,record=call(case,stage,attempt,context_for(state))
                evaluate(raw,state,output/(case+'-plan-0'),0)
            else:
                baseline=output/(case+'-plan-0');raw=_read(baseline,'compact-plan.json');report=_read(baseline,'relations.json')
                scope=local.scope(raw,report);context=context_for(state)
                context.update(previous_compact_plan=raw,application_feedback=previous.repair.feedback(report,_read(baseline,'repair-baseline.json')),
                    locked_assembly=_read(baseline,'assembly-lock.json'),locked_arrangement_bindings=_read(baseline,'arrangement-bindings.json'))
                patch,record=call(case,stage,attempt,context,raw,scope)
                folder=output/(case+'-plan-1');folder.mkdir(exist_ok=True);prior.write(folder/'repair-scope.json',scope);prior.write(folder/'patch.json',patch)
                revised,audit=local.apply(raw,patch,scope,state['contract']);prior.write(folder/'patch-audit.json',audit)
                state['trace'].append({'stage':'patch_admission','allowed_parts':scope['allowed_parts'],**audit})
                if revised is None:state['status']='repair_unsupported'
                else:evaluate(revised,state,folder,1,baseline)
            record['status']='done';persist()
        except background.Pending as error:
            operations[op].update(status='pending',error=str(error));stopped.append('retrieval_pending');persist();break
        except prior.CommandError as error:
            operations.setdefault(op,{}).update(status='halted',error=str(error));stopped.append(str(error));persist();break
        except (ValueError,KeyError,TypeError) as error:
            operations.setdefault(op,{}).update(status='rejected',error=str(error));state.update(status=stage+'_rejected',error=str(error));persist()
    prior.write(output/'assessment.json',previous.assess(states,output))
    summary=ledger.summary();prior.write(output/'spending.json',{'charged_and_held_nanos':BATCH.spent(ledger),
        'daily_remaining_nanos':summary['remaining_nanos'],'daily_limit_nanos':summary['daily_limit_nanos'],'stopped':stopped,'actual_invoiced_cost':None})
    prior.write(output/'index.json',[{'name':p.name} for p in sorted(output.iterdir()) if p.is_dir() and (p/'package.json').exists()])
    (output/'index.html').write_text((SOURCE/'viewer.html').read_text());persist()
    print(json.dumps({'status':stopped or 'finished','charged_and_held_usd':BATCH.spent(ledger)/1e9,
        'cases':[{k:s[k] for k in ('case','status','geometry_executed')} for s in states.values()],'invocation_seconds':time.perf_counter()-started}),flush=True)
    return states


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--resume',action='store_true');args=p.parse_args()
    if args.resume:
        protocol=_read(args.output,'protocol.json');states={s['case']:s for s in _read(args.output,'result.json')['cases']}
        if protocol['experiment']!=BATCH.experiment or frozen_sources()!=protocol['files_sha256']:raise prior.CommandError('Resume requires unchanged frozen experiment')
    else:
        args.output.mkdir(parents=True,exist_ok=False);states=initialize(args.output)
        protocol={'experiment':BATCH.experiment,'files_sha256':frozen_sources(),'specs':SPECS,'allowed_operations':OPERATIONS,
            'budget_nanos':BATCH.budget,'prior_upper_bound_nanos':BATCH.prior_upper_bound,'aggregate_limit_nanos':BATCH.aggregate_limit,
            'policies':{s:selected(s) for s in ('extract','plan','patch')},'background':True,'store':False,
            'job_deadline_seconds':360,'full_validation':True,'geometry_executor_changed':False,'execute':args.execute}
        prior.write(args.output/'protocol.json',protocol);prior.write(args.output/'result.json',{'cases':list(states.values()),'native_generation_goal_passed':False})
    if not args.execute:return
    with open(ROOT/'.oryn-usage'/(BATCH.experiment+'.lock'),'a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ledger=prior.UsageLedger();key=prior.MacKeychain(account=b'openai-api-key').load()
        if not key:raise prior.CommandError('Model connection unavailable')
        run(args.output,ledger,key,protocol,states)

if __name__=='__main__':main()
