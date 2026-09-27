import copy
import json
import multiprocessing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
from cognition import CommandError, offline_intent
from spending import policy, quote_cost, PRICE_REVIEWED, PRICE_EXPIRES, DAILY_LIMIT
from usage_ledger import UsageLedger
from paid_gateway import PaidGateway
from cognitive_providers import priced_body, openai_json, count_input
from test_commands import fixture, FakeTransport
from command_app import Commands


def reserve_worker(path, ident, fingerprint, amount, now, output):
    ledger = UsageLedger(path, clock=lambda:now)
    try:
        ledger.reserve(ident,'developer',fingerprint,amount)
        output.put(True)
    except CommandError:
        output.put(False)


class SpendingTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.path = Path(folder.name)/'usage.sqlite3'
        self.now = PRICE_REVIEWED+100
        self.clock = lambda:self.now
        self.ledger = UsageLedger(self.path,clock=self.clock)
        self.sent = []; self.counted = []
        def count(key,body): self.counted.append(copy.deepcopy(body)); return 500
        def send(key,body):
            self.sent.append(copy.deepcopy(body))
            return {'model':body['model'],'service_tier':'default','status':'completed',
                    'usage':{'input_tokens':500,'output_tokens':100},
                    'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(offline_intent('Isolate this'))}]}]}
        self.gateway = PaidGateway(self.ledger,counter=count,sender=send,clock=self.clock)
        self.state = fixture()

    def quote(self, profile='routine'):
        return self.gateway.prepare('openai',profile,'fake-key-for-test','Isolate this',self.state,'quest','credential-v1')

    def run_quote(self,q,**changes):
        data = {'id':q['request_id'],'approvePaid':True,'approvedCostNanos':q['reserved_nanos']}
        args = dict(provider='openai',profile=q['profile'],key='fake-key-for-test',question='Isolate this',state=self.state,serial='quest',credential_revision='credential-v1')
        args.update(changes)
        return self.gateway.run(data,**args)

    def test_policy_tiers_and_unknowns(self):
        for profile, model, effort, cap in [('routine','gpt-6-sol','medium',30000000),('question_high','gpt-6-sol','high',50000000),('benchmark','gpt-6-astra','medium',100000000)]:
            p=policy('openai',profile,self.now)
            self.assertEqual((p['model'],p['effort'],p['ceiling_nanos']),(model,effort,cap))
        for provider,profile in [('gemini','routine'),('openai','ultra'),('openai','max'),('openai','persistent')]:
            with self.assertRaises(CommandError): policy(provider,profile,self.now)
        for now in [PRICE_REVIEWED-1, PRICE_EXPIRES]:
            with self.assertRaises(CommandError): policy('openai','routine',now)

    def test_cost_uses_integer_worst_input_and_output(self):
        p=policy('openai','routine',self.now)
        self.assertEqual(quote_cost(p,500),500*2500+1024*10000)
        for count in [True,0,-1,16001,1.5,None,16000]:
            with self.assertRaises(CommandError): quote_cost(p,count)

    def test_quote_no_generation_and_identical_count_payload(self):
        q=self.quote()
        self.assertEqual(self.sent,[])
        self.assertEqual(self.ledger.summary()['charged_and_reserved_nanos'],0)
        self.run_quote(q)
        self.assertEqual(self.sent,self.counted)
        body=self.sent[0]
        self.assertEqual(body['reasoning'],{'effort':'medium'})
        self.assertEqual(body['service_tier'],'default')
        self.assertFalse(body['store'])
        self.assertNotIn('tools',body)

    def test_cost_settlement_not_invoice(self):
        q=self.quote(); self.run_quote(q)
        row=self.ledger.get(q['request_id'])
        self.assertEqual(row['status'],'completed')
        self.assertEqual(row['calculated_cost_nanos'],500*2500+100*10000)
        self.assertIsNone(row['actual_cost_nanos'])
        self.assertLess(row['charged_nanos'],q['reserved_nanos'])
        self.assertNotIn('fake-key-for-test',self.path.read_bytes().decode(errors='ignore'))
        self.assertNotIn('Isolate this',self.path.read_bytes().decode(errors='ignore'))

    def test_changed_request_context_provider_or_credentials(self):
        q=self.quote()
        changed=copy.deepcopy(self.state); changed['contextToken']='0'*32
        for args in [{'question':'Explode'}, {'state':changed},{'credential_revision':'v2'},{'profile':'benchmark'},{'serial':'other'},{'provider':'gemini'}]:
            with self.subTest(args=args), self.assertRaises(CommandError): self.run_quote(q,**args)
        self.assertEqual(self.sent,[])

    def test_exact_amount_and_explicit_consent(self):
        q=self.quote()
        for data in [{'id':q['request_id'],'approvePaid':False,'approvedCostNanos':q['reserved_nanos']},
                     {'id':q['request_id'],'approvePaid':True,'approvedCostNanos':q['reserved_nanos']+1}]:
            with self.assertRaises(CommandError): self.gateway.run(data,'openai','routine','fake-key-for-test','Isolate this',self.state,'quest','credential-v1')
        self.assertEqual(self.sent,[])

    def test_expiry_and_policy_expiry(self):
        q=self.quote(); self.now+=121
        with self.assertRaises(CommandError): self.run_quote(q)
        self.now=PRICE_EXPIRES-10; q=self.quote(); self.now=PRICE_EXPIRES
        with self.assertRaises(CommandError): self.run_quote(q)

    def test_duplicate_and_restart_never_resend(self):
        q=self.quote(); self.run_quote(q)
        with self.assertRaises(CommandError): self.run_quote(q)
        restarted=PaidGateway(UsageLedger(self.path,clock=self.clock),counter=lambda *_:500,sender=self.gateway.sender,clock=self.clock)
        with self.assertRaises(CommandError): restarted.run({'id':q['request_id'],'approvePaid':True},'openai','routine','fake-key-for-test','Isolate this',self.state,'quest','credential-v1')
        self.assertEqual(len(self.sent),1)
        self.assertEqual(restarted.ledger.summary()['charged_and_reserved_nanos'],2250000)

    def test_timeout_and_crash_keep_reservation_across_midnight(self):
        q=self.quote()
        def fail(*_): raise TimeoutError('private response')
        self.gateway.sender=fail
        with self.assertRaises(CommandError): self.run_quote(q)
        self.assertEqual(self.ledger.get(q['request_id'])['status'],'uncertain')
        self.now+=86400
        self.assertEqual(UsageLedger(self.path,clock=self.clock).summary()['charged_and_reserved_nanos'],q['reserved_nanos'])
        q2=self.quote(); self.ledger.reserve(q2['request_id'],'developer',q2['fingerprint'],q2['reserved_nanos'])
        self.assertEqual(UsageLedger(self.path,clock=self.clock).get(q2['request_id'])['status'],'reserved')

    def test_untrusted_usage_halts_paid_calls(self):
        q=self.quote()
        self.gateway.sender=lambda *_:{'usage':{'input_tokens':500,'output_tokens':999999}}
        with self.assertRaises(CommandError): self.run_quote(q)
        self.assertTrue(self.ledger.summary()['halted'])
        self.assertEqual(self.ledger.summary()['charged_and_reserved_nanos'],q['reserved_nanos'])
        with self.assertRaises(CommandError): self.quote()

    def test_incomplete_or_refusal_still_accounts_for_usage(self):
        q=self.quote(); sender=self.gateway.sender
        def incomplete(*args):
            result=sender(*args); result['status']='incomplete'; return result
        self.gateway.sender=incomplete
        with self.assertRaises(CommandError): self.run_quote(q)
        self.assertEqual(self.ledger.get(q['request_id'])['outcome'],'invalid_response')
        self.assertGreater(self.ledger.summary()['charged_and_reserved_nanos'],0)

    def test_budget_atomic_across_processes(self):
        # Seed earlier unresolved usage to leave room for exactly one real quote.
        seed=self.quote(); seeded=dict(seed,request_id=uuid.uuid4().hex,reserved_nanos=DAILY_LIMIT-seed['reserved_nanos'],ceiling_nanos=DAILY_LIMIT)
        self.ledger.create_quote(seeded)
        self.ledger.reserve(seeded['request_id'],'developer',seeded['fingerprint'],seeded['reserved_nanos'])
        q1=self.quote(); q2=self.quote()
        ctx=multiprocessing.get_context('spawn'); output=ctx.Queue()
        processes=[ctx.Process(target=reserve_worker,args=(str(self.path),q['request_id'],q['fingerprint'],q['reserved_nanos'],self.now,output)) for q in (q1,q2)]
        for p in processes:p.start()
        for p in processes:p.join(15); self.assertEqual(p.exitcode,0)
        self.assertEqual(sorted(output.get(timeout=2) for _ in processes),[False,True])
        self.assertEqual(self.ledger.summary()['remaining_nanos'],0)

    def test_clock_rollback_and_corruption_fail_closed(self):
        q=self.quote(); self.now-=1
        with self.assertRaises(CommandError): self.run_quote(q)
        self.assertTrue(self.ledger.summary()['halted'])
        self.path.write_bytes(b'not a database')
        with self.assertRaises(CommandError): self.ledger.summary()

    def test_gateway_must_reserve_before_network(self):
        q=self.quote(); sender=self.gateway.sender
        def observe(*args):
            self.assertEqual(UsageLedger(self.path,clock=self.clock).get(q['request_id'])['status'],'reserved')
            return sender(*args)
        self.gateway.sender=observe; self.run_quote(q)

    def test_http_client_fixed_endpoint_and_no_retries(self):
        class Opener:
            calls=0
            def open(self, request, timeout):
                self.calls+=1
                assert request.full_url=='https://api.openai.com/v1/responses/input_tokens'
                raise TimeoutError('secret must not leak')
        opener=Opener()
        with self.assertRaises(CommandError) as caught: openai_json('responses/input_tokens','fake-key',{},opener)
        self.assertNotIn('secret must not leak',str(caught.exception)); self.assertEqual(opener.calls,1)
        with self.assertRaises(CommandError): openai_json('../billing','fake-key',{},opener)

    def test_count_endpoint_preserves_schema_and_excludes_generation_fields(self):
        body=priced_body(policy('openai','routine',self.now),'Isolate this',self.state)
        with patch('cognitive_providers.openai_json',return_value={'input_tokens':500}) as call:
            self.assertEqual(count_input('fake-key',body),500)
            endpoint,key,payload=call.call_args.args
            self.assertEqual(endpoint,'responses/input_tokens')
            self.assertEqual(set(payload),{'model','input','reasoning','text'})
            self.assertEqual(payload['text'],body['text'])
            self.assertEqual(payload['input'],body['input'])
        with self.assertRaises(CommandError):count_input('fake-key',dict(body,tools=[]))

    def test_existing_damaged_schema_is_not_reset(self):
        with self.ledger.connection() as db:db.execute('DROP TABLE usage');db.commit()
        with self.assertRaises(CommandError):UsageLedger(self.path,clock=self.clock)

    def test_service_blocks_old_paid_checkbox_and_gemini(self):
        service=Commands(FakeTransport(),gateway=self.gateway)
        with self.assertRaises(CommandError):service.configure({'provider':'gemini','key':'fake-key-for-test'})
        service.configure({'provider':'openai','profile':'routine','key':'fake-key-for-test'})
        response=service.ask({'id':uuid.uuid4().hex,'provider':'openai','profile':'routine','question':'Isolate this','approvePaid':True})
        self.assertIsNone(response['action']); self.assertEqual(self.sent,[])


if __name__=='__main__':unittest.main()
