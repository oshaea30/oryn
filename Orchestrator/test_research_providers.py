"""All HTTP and paid generation mocked; real SQLite admission/settlement."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from cognition import CommandError
from research_providers import WikipediaRetrieval, OpenAICognitiveProvider, research_body
from spending import policy, PRICE_REVIEWED, PRICE_EXPIRES
from test_investigation import source, findings
from usage_ledger import UsageLedger


class RetrievalTests(unittest.TestCase):
    def retrieve(self, value):
        opener=Mock(); opener.open.return_value=io.BytesIO(value if isinstance(value,bytes) else json.dumps(value).encode())
        return WikipediaRetrieval(opener=opener),opener

    def test_fixed_host_result_limits_rank_and_unverified_revision(self):
        provider,opener=self.retrieve({'query':{'pages':[
            {'pageid':2,'index':2,'title':'Other','extract':'other'},
            {'pageid':1,'index':1,'title':'V8 engine','extract':'engine'}]}})
        results=provider.retrieve('a V8 engine')
        self.assertEqual([r['id'] for r in results],['wiki-1','wiki-2'])
        self.assertEqual(results[0]['url'],'https://en.wikipedia.org/?curid=1')
        self.assertIsNone(results[0]['revision_match'])
        request=opener.open.call_args.args[0]
        self.assertTrue(request.full_url.startswith('https://en.wikipedia.org/w/api.php?'))
        self.assertIn('gsrlimit=5',request.full_url)
        self.assertIn('gsrsearch=V8+engine',request.full_url)
        self.assertEqual(opener.open.call_args.kwargs['timeout'],20)
        self.assertIsNone(request.get_header('Authorization'))

    def test_empty_search_is_not_a_fake_success(self):
        provider,_=self.retrieve({'batchcomplete':True})
        self.assertEqual(provider.retrieve('unfindable'),[])

    def test_malformed_huge_and_error_responses_fail_without_retry(self):
        for value in (b'x'*262145, {'error':{'info':'PRIVATE_TOKEN'}}, {'query':{'pages':'bad'}},
                      {'query':{'pages':[{'pageid':1,'title':'x','extract':'x'}]*6}}):
            provider,opener=self.retrieve(value)
            with self.assertRaises(ValueError) as caught: provider.retrieve('engine')
            self.assertNotIn('PRIVATE_TOKEN',str(caught.exception)); opener.open.assert_called_once()


class CognitiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.now=PRICE_REVIEWED+3600
        self.ledger=UsageLedger(Path(self.temp.name)/'usage.sqlite3',clock=lambda:self.now)
        self.counter=Mock(return_value=1000)
        self.sender=Mock(side_effect=self.response)
        self.provider=OpenAICognitiveProvider(self.ledger,'SECRET_FIXTURE',self.counter,self.sender,clock=lambda:self.now)
        self.request={'query':'V8 engine','sources':[source()], 'geometry':{'piece_count':200,'prioritized_count':8}}

    def tearDown(self): self.temp.cleanup()

    def response(self,*args):
        return {'status':'completed','model':'gpt-6-sol','service_tier':'default',
            'usage':{'input_tokens':1000,'output_tokens':200},
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(findings())}]}]}

    def test_no_dialog_reserve_before_call_then_settle_shared_ledger(self):
        def send(*args):
            row=self.ledger.get('a'*32)
            self.assertEqual(row['status'],'reserved')
            self.assertLessEqual(row['reserved_nanos'],50_000_000)
            self.assertEqual(row['operation'],'reference_investigation')
            return self.response()
        self.sender.side_effect=send
        result=self.provider.investigate('a'*32,self.request)
        self.assertEqual(result['findings'],findings())
        self.assertIsNone(result['cost']['actual_nanos'])
        self.assertEqual(result['cost']['calculated_nanos'],4_500_000)
        self.assertEqual(self.ledger.get('a'*32)['status'],'completed')
        self.assertEqual(self.ledger.summary()['charged_and_reserved_nanos'],4_500_000)
        self.assertNotIn(b'SECRET_FIXTURE',self.ledger.path.read_bytes())
        with self.assertRaises(CommandError): self.provider.investigate('a'*32,self.request)
        self.sender.assert_called_once(); self.counter.assert_called_once()

    def test_payload_is_text_only_tools_free_and_bounded(self):
        body=research_body(policy('openai','question',self.now),self.request)
        self.assertNotIn('tools',body); self.assertFalse(body['store'])
        self.assertEqual(body['max_output_tokens'],1024)
        sent=json.loads(body['input'][1]['content'])
        self.assertEqual(set(sent),{'object_request','source_excerpts','geometry'})
        self.assertNotIn('url',sent['source_excerpts'][0])
        self.assertNotIn('asset_id',sent['geometry'])
        bad=deepcopy(self.request); bad['geometry']['glb']='NOT_ALLOWED'
        with self.assertRaises(CommandError): research_body(policy('openai','question',self.now),bad)

    def test_cost_over_ceiling_never_dispatches(self):
        self.counter.return_value=16000
        with self.assertRaises(CommandError): self.provider.investigate('a'*32,self.request)
        self.sender.assert_not_called(); self.assertIsNone(self.ledger.get('a'*32))

    def test_expired_review_blocks_even_token_counting(self):
        self.now=PRICE_EXPIRES
        with self.assertRaises(CommandError): self.provider.investigate('a'*32,self.request)
        self.counter.assert_not_called(); self.sender.assert_not_called()

    def test_shared_budget_halt_blocks_research(self):
        with self.ledger.transaction() as db: db.execute('UPDATE control SET halted=1')
        with self.assertRaises(CommandError): self.provider.investigate('a'*32,self.request)
        self.counter.assert_not_called(); self.sender.assert_not_called()

    def test_existing_command_reservation_exhausts_same_daily_budget(self):
        quote={'request_id':'b'*32,'actor_id':'developer','provider':'openai','profile':'fixture',
            'model':'gpt-6-sol','effort':'medium','operation':'intent_interpretation','fingerprint':'fixture',
            'price_version':'fixture','input_tokens':1000,'max_output_tokens':1024,
            'reserved_nanos':2_000_000_000,'ceiling_nanos':2_000_000_000,'created':self.now,'expires':self.now+120}
        self.ledger.create_quote(quote); self.ledger.reserve('b'*32,'developer','fixture',2_000_000_000)
        with self.assertRaises(CommandError): self.provider.investigate('a'*32,self.request)
        self.counter.assert_not_called(); self.sender.assert_not_called()

    def test_timeout_holds_reservation_and_never_retries(self):
        self.sender.side_effect=RuntimeError('SECRET_FIXTURE')
        with self.assertRaises(CommandError) as caught: self.provider.investigate('a'*32,self.request)
        self.assertNotIn('SECRET_FIXTURE',str(caught.exception))
        self.assertEqual(self.ledger.get('a'*32)['status'],'uncertain')
        with self.assertRaises(CommandError): self.provider.investigate('a'*32,self.request)
        self.sender.assert_called_once()

    def test_unreconciled_model_halts_all_paid_cognition(self):
        self.sender.side_effect=lambda *args:dict(self.response(),model='unreviewed-model')
        with self.assertRaises(CommandError): self.provider.investigate('a'*32,self.request)
        self.assertTrue(self.ledger.summary()['halted'])
        self.assertEqual(self.ledger.get('a'*32)['status'],'uncertain')

    def test_bad_citations_settle_usage_but_publish_no_findings(self):
        response=self.response(); response['output'][0]['content'][0]['text']=json.dumps(findings('invented'))
        self.sender.side_effect=None; self.sender.return_value=response
        with self.assertRaises(CommandError): self.provider.investigate('a'*32,self.request)
        self.assertEqual(self.ledger.get('a'*32)['outcome'],'invalid_response')


if __name__=='__main__': unittest.main()
