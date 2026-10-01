"""Durable, at-most-one creation of bounded background Responses jobs.

GET failures preserve the response ID and reservation. Resume polls that same job;
a POST with no acknowledged ID is never automatically repeated. No secret logging.
Docs: https://developers.openai.com/api/docs/guides/background (checked 2026-10-01).
"""
from copy import deepcopy
import fcntl
import json
import os
import re
import time
import urllib.request
from Research.native_objects import meaning_experiment as transport

prior=transport.prior
ACTIVE={'queued','in_progress'}
TERMINAL={'completed','failed','cancelled','incomplete'}

class Pending(prior.CommandError):pass


def save(path,value):
    data=json.dumps(value,indent=2,allow_nan=False)+'\n';temp=path.with_suffix(path.suffix+'.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def exchange(method,suffix,key,body=None):
    if suffix and not re.fullmatch(r'/resp_[A-Za-z0-9_-]{1,180}(/cancel)?',suffix):raise ValueError('Invalid response path')
    request=urllib.request.Request('https://api.openai.com/v1/responses'+suffix,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method=method)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),transport.NoRedirect())
    with opener.open(request,timeout=30) as response:raw=response.read(262145)
    if len(raw)>262144:raise ValueError('Response size limit')
    return json.loads(raw)


def dispatch(ident,p,body,folder,ledger,key,batch,*,sender=exchange,counter=None,clock=time.time,
             sleeper=time.sleep,wait_seconds=360,poll_seconds=5):
    if ident not in {batch.operation_id(c) for c in batch.cases}:raise prior.CommandError('Operation outside frozen background batch')
    reviewed_deadline=900 if p.get('profile')=='research_astra_xhigh' else 360
    if wait_seconds!=reviewed_deadline or not 1<=poll_seconds<=10:raise prior.CommandError('Unreviewed background wait policy')
    count_body=deepcopy(body)  # Background/metadata do not alter model input; retain the existing strict count adapter.
    body=deepcopy(body);body.update(background=True,store=False,metadata={'oryn_operation':ident})
    fingerprint=prior.digest(body);folder.mkdir(parents=True,exist_ok=True)
    with open(folder/'job.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if ledger.summary()['halted']:raise prior.CommandError('Shared ledger halted')
        path=folder/'job.json';row=ledger.get(ident)
        if path.exists():
            state=json.loads(path.read_text())
            if state['operation_id']!=ident or state['body_sha256']!=fingerprint:raise prior.CommandError('Resumed job body/identity changed')
            if row is None or row['fingerprint']!=fingerprint:raise prior.CommandError('Resumed job reservation missing or changed')
            if not state.get('response_id'):raise prior.CommandError('Unacknowledged creation; no retry or duplicate dispatch')
        else:
            if row:raise prior.CommandError('Operation already claimed; resume its original journal only')
            save(folder/'request.json',{'body':body,'body_sha256':fingerprint})
            count=(counter or prior.count_input)(key,count_body);amount=prior.quote_cost(p,count);now=int(clock())
            spent=batch.spent(ledger)
            if spent+amount>batch.budget or batch.prior_upper_bound+spent+amount>batch.aggregate_limit:raise prior.CommandError('Research spending ceiling reached')
            quote={'request_id':ident,'actor_id':'developer','provider':'openai','profile':p['profile'],'model':p['model'],'effort':p['effort'],
                'operation':batch.experiment,'fingerprint':fingerprint,'price_version':p['price_version'],'input_tokens':count,
                'max_output_tokens':p['max_output_tokens'],'reserved_nanos':amount,'ceiling_nanos':p['ceiling_nanos'],
                'created':now,'expires':min(now+120,prior.PRICE_EXPIRES)}
            ledger.create_quote(quote);ledger.reserve(ident,'developer',fingerprint,amount)
            state={'operation_id':ident,'body_sha256':fingerprint,'started':clock(),'deadline':clock()+wait_seconds,
                   'response_id':None,'status':'dispatching','events':[],'creation_calls':1,'poll_calls':0,'cancel_calls':0}
            save(path,state);row=ledger.get(ident)
            try:response=sender('POST','',key,body)
            except Exception as error:
                state.update(status='unacknowledged',failure_category=transport.failure_category(error));save(path,state);ledger.uncertain(ident)
                message='Provider funding required' if state['failure_category']=='provider_funding_required' else 'Creation outcome unknown; reservation held; no retry'
                raise prior.CommandError(message) from None
            _accept(response,state,path,ledger,ident,clock)
        terminal=folder/'response.json'
        # Save terminal data before settling. Restart can safely complete or read settlement.
        if terminal.exists():return _finish(json.loads(terminal.read_text()),state,row,folder,ledger,clock)
        if state['status'] in TERMINAL:
            try:response=sender('GET','/'+state['response_id'],key,None)
            except Exception:raise Pending('Retrieve retained terminal job without recreating it') from None
            _accept(response,state,path,ledger,ident,clock)
        while state['status'] in ACTIVE:
            method='GET';suffix='/'+state['response_id'];payload=None
            if clock()<state['deadline']:sleeper(min(poll_seconds,max(0,state['deadline']-clock())))
            if clock()>=state['deadline']:method='POST';suffix+='/cancel';payload={};state['cancel_calls']+=1
            else:state['poll_calls']+=1
            save(path,state)
            try:response=sender(method,suffix,key,payload)
            except Exception as error:
                state['events'].append({'elapsed_seconds':clock()-state['started'],'event':'retrieval_unavailable','category':transport.failure_category(error)})
                save(path,state)
                raise Pending('Saved response ID retained; resume retrieval without a new generation') from None
            _accept(response,state,path,ledger,ident,clock)
            if method=='POST' and state['status'] in ACTIVE:
                raise Pending('Cancellation pending; resume the same response, never recreate')
        if not terminal.exists():raise prior.CommandError('Terminal response missing; reservation retained')
        return _finish(json.loads(terminal.read_text()),state,row,folder,ledger,clock)


def _accept(response,state,path,ledger,ident,clock):
    if not isinstance(response,dict):
        ledger.uncertain(ident,halt=True);raise prior.CommandError('Unexpected background response; reservation retained')
    rid=response.get('id');status=response.get('status')
    if not isinstance(rid,str) or not re.fullmatch(r'resp_[A-Za-z0-9_-]{1,180}',rid) or status not in ACTIVE|TERMINAL or state['response_id'] not in (None,rid):
        ledger.uncertain(ident,halt=True);raise prior.CommandError('Unexpected background response identity/status; reservation retained')
    state['response_id']=rid;state['status']=status
    state['events'].append({'elapsed_seconds':clock()-state['started'],'event':status})
    save(path,state)
    if status in TERMINAL:save(path.parent/'response.json',response)


def _finish(response,state,quote,folder,ledger,clock):
    try:incoming,outgoing,amount=prior.settled_usage(response,quote)
    except prior.CommandError:ledger.uncertain(state['operation_id'],halt=True);raise
    current=ledger.get(state['operation_id'])
    if current['status']=='reserved':ledger.settle(state['operation_id'],incoming,outgoing,amount,'completed' if response['status']=='completed' else 'invalid_response')
    elif current['status']!='completed' or current['calculated_cost_nanos']!=amount:raise prior.CommandError('Unexpected background settlement state')
    meta={'operation_id':state['operation_id'],'response_id':state['response_id'],'status':response['status'],
          'incomplete_details':response.get('incomplete_details'),'usage':response['usage'],'calculated_cost_nanos':amount,
          'dispatch_seconds':state['events'][-1]['elapsed_seconds'],'creation_calls':state['creation_calls'],
          'poll_calls':state['poll_calls'],'cancel_calls':state['cancel_calls'],'background':True}
    save(folder/'response-metadata.json',meta)
    return prior.parse(response),meta
