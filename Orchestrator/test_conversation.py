from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock

from cognition import CommandError
from complete_object import ACTIONS, binding, decide, validate_state, propulsion_explanation
from conversation import Conversation
from experience_interpreter import ExperienceInterpreter
from spending import PRICE_REVIEWED
from usage_ledger import UsageLedger


def intent(kind, target='none', ident=''):
    return {'intent': kind, 'target': target, 'id': ident}


def state():
    components = []
    for ident, parent, driver in [('motor_0', '', ''), ('rotor_0', 'motor_0', ''), ('propeller_0', 'rotor_0', 'rotor_0')]:
        components.append({'id': ident, 'geometryId': ident, 'name': ident.replace('_', ' '), 'subsystem': 'propulsion',
            'parentId': parent, 'driverId': driver, 'explanation': 'In this authored model, '+ident+' belongs to propulsion.',
            'provenance': 'human_authored', 'evidence': 'unsupported', 'referenceIds': []})
    return {'schema': 1, 'session': 'a'*32, 'contextToken': 'b'*32, 'referenceToken': 'f'*32, 'utc': int(time.time()), 'selected': 'motor_0',
        'ready': True, 'running': False, 'isolated': False, 'partsMode': True, 'speed': 1, 'spread': 0,
        'subject': {'id': 'authored-drone-propulsion', 'revision': '1', 'instance': '1', 'title': 'Drone',
            'scope': 'authored_family_demonstration', 'explanation': 'Authored example; no flight simulation.',
            'actions': list(ACTIONS[1:]), 'components': components}}


def drone_state():
    s = state()
    first = deepcopy(s['subject']['components'])
    for i in range(1, 4):
        for original in first:
            c = deepcopy(original)
            for key in ('id', 'geometryId', 'parentId', 'driverId'):
                c[key] = c[key].replace('_0', f'_{i}')
            s['subject']['components'].append(c)
    return validate_state(s)


class ContractTests(unittest.TestCase):
    def test_state_bounds_and_false_evidence(self):
        self.assertEqual(validate_state(state())['selected'], 'motor_0')
        for mutate in [lambda s:s.update(utc=0), lambda s:s.update(speed=float('nan')),
                       lambda s:s.update(selected='invented'),
                       lambda s:s['subject']['components'][0].update(evidence='verified'),
                       lambda s:s['subject']['components'][0].update(parentId='propeller_0')]:
            s=state();mutate(s)
            with self.assertRaises(CommandError):validate_state(s)

    def test_selected_answers_only_use_authored_record(self):
        s=state();r=decide(s,intent('describe','selected'))
        self.assertEqual(r['answer'],s['subject']['components'][0]['explanation'])
        self.assertEqual(r['evidence'][0]['status'],'unsupported')
        self.assertIsNone(r['action'])

    def test_why_subsystem_uses_declared_driver(self):
        s=state();memory={'binding':binding(s),'subject':{'target':'subsystem','id':'propulsion'}}
        result=decide(s,intent('why','previous'),memory)
        self.assertIn('rotor 0 drives propeller 0',result['answer'])
        self.assertNotIn('thrust',result['answer'])
        s['selected']='propeller_0'
        self.assertIn('no longer clear',decide(s,intent('why','previous'),memory)['answer'])

    def test_reference_does_not_revive_after_selection_changes_away_and_back(self):
        s=state();memory={'binding':binding(s),'subject':{'target':'component','id':'motor_0'}}
        s['referenceToken']='e'*32
        self.assertIn('no longer clear',decide(s,intent('why','previous'),memory)['answer'])

    def test_show_me_keeps_previous_component(self):
        s=state();memory={'binding':binding(s),'subject':{'target':'component','id':'motor_0'}}
        r=decide(s,intent('demonstrate','previous'),memory)
        self.assertEqual((r['action'],r['component']),('demonstrate','motor_0'))

    def test_unknown_target_and_invented_action_never_execute(self):
        self.assertIsNone(decide(state(),intent('select','component','fake'))['action'])
        with self.assertRaises(CommandError):decide(state(),intent('delete'))
        self.assertIsNone(decide(state(),intent('unknown'))['action'])
        with self.assertRaises(CommandError):decide(state(),dict(intent('play'),code='execute'))

    def test_general_propulsion_answer_preserves_model_uncertainty(self):
        s=drone_state();before=deepcopy(s)
        result=decide(s,intent('describe','subsystem','propulsion'))
        self.assertIn('push air downward',result['answer'])
        self.assertIn('does not calculate thrust or prove it could fly',result['answer'])
        self.assertIsNone(result['action'])
        self.assertEqual(result['explanationScope'],'general_principle_and_authored_model')
        self.assertEqual(result['sources'][0]['scope'],'general_propeller_thrust')
        self.assertEqual({e['status'] for e in result['evidence']},{'unsupported'})
        self.assertEqual(result['references'],[],'General source does not become mesh evidence')
        self.assertEqual(s,before)
        self.assertLessEqual(len(result['answer']),480,'Full limitation fits the headset notice')

    def test_propulsion_principle_requires_reviewed_definition_and_drive_bindings(self):
        for mutate in [lambda s:s.update(subject=None),
                       lambda s:s['subject'].update(id='generated-drone'),
                       lambda s:s['subject'].update(revision='2'),
                       lambda s:s['subject'].update(scope='generated'),
                       lambda s:s['subject']['components'].pop(),
                       lambda s:s['subject']['components'][2].update(driverId='')]:
            s=drone_state();mutate(s)
            self.assertIsNone(propulsion_explanation(s.get('subject')))

    def test_show_drone_from_empty_workspace(self):
        s=state();s.update(subject=None,selected='')
        validate_state(s)
        self.assertEqual(decide(s,intent('show_drone'))['action'],'show_drone')
        self.assertIsNone(decide(s,intent('play'))['action'])


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'conversation.sqlite3'
        self.state=state();self.now=time.time();self.calls=[]
        self.transport=Mock();self.transport.snapshot.side_effect=lambda:('device',deepcopy(self.state))
        self.transport.receipt.return_value={'status':'waiting','message':'Waiting'}
        self.provider=Mock();self.provider.interpret.return_value=intent('describe','selected')
        self.factory=lambda:self.provider
        self.app=Conversation(self.path,self.factory,self.transport,clock=lambda:self.now)
        self.request={'id':'c'*32,'question':'What does this do?'}
    def tearDown(self):self.temp.cleanup()

    def test_application_calls_provider_and_answers_without_codex(self):
        r=self.app.ask(self.request)
        self.assertEqual(r['status'],'completed');self.assertIn('motor_0',r['answer'])
        self.provider.interpret.assert_called_once();self.transport.send.assert_not_called()
        self.assertEqual(self.app.memory(self.state)['subject']['id'],'motor_0')

    def test_flight_question_uses_scoped_answer_and_keeps_followup_subject(self):
        self.state=drone_state();self.app.feedback=Mock()
        self.provider.interpret.return_value=intent('describe','subsystem','propulsion')
        result=self.app.ask(dict(self.request,question='What makes this drone fly?'))
        self.assertEqual(result['status'],'completed');self.assertIsNone(result['action'])
        self.transport.send.assert_not_called()
        self.assertEqual(self.app.current(self.request['id'])['intent'],intent('describe','subsystem','propulsion'))
        self.assertEqual(self.app.memory(self.state)['subject'],{'target':'subsystem','id':'propulsion'})
        self.assertEqual(self.app.feedback.publish.call_args.args[1]['message'],result['answer'])
        self.provider.interpret.return_value=intent('isolate_subsystem','previous')
        result=self.app.ask({'id':'d'*32,'question':'Show only that subsystem'})
        self.assertEqual((result['action'],result['subsystem']),('isolate_subsystem','propulsion'))

    def test_duplicate_and_restart_never_repeat_provider_or_command(self):
        self.provider.interpret.return_value=intent('play')
        r=self.app.ask(self.request);self.assertEqual(r['status'],'pending')
        self.app.ask(self.request)
        again=Conversation(self.path,self.factory,self.transport,clock=lambda:self.now)
        again.ask(self.request)
        self.provider.interpret.assert_called_once();self.transport.send.assert_called_once()
        with self.assertRaises(CommandError):again.ask(dict(self.request,question='pause'))

    def test_selection_changes_during_reasoning_reject_answer_and_action(self):
        def interpret(*_):
            self.state['contextToken']='d'*32;self.state['selected']='propeller_0'
            return intent('isolate_component','selected')
        self.provider.interpret.side_effect=interpret
        r=self.app.ask(self.request)
        self.assertEqual(r['status'],'failed');self.assertIn('selection changed',r['answer'])
        self.transport.send.assert_not_called()

    def test_held_object_can_be_described_but_motion_not_queued(self):
        self.state['ready']=False
        self.assertEqual(self.app.ask(self.request)['status'],'completed')
        self.provider.interpret.return_value=intent('play')
        self.assertEqual(self.app.ask(dict(self.request,id='d'*32))['status'],'failed')
        self.transport.send.assert_not_called()

    def test_receipt_precedes_followup_memory(self):
        self.provider.interpret.return_value=intent('isolate_subsystem','subsystem','propulsion')
        self.assertEqual(self.app.ask(self.request)['status'],'pending')
        self.assertIsNone(self.app.memory(self.state))
        self.state.update(selected='',contextToken='d'*32,isolated=True)
        self.transport.receipt.return_value={'status':'executed','message':'Applied','referenceToken':self.state['referenceToken']}
        self.assertEqual(self.app.get(self.request['id'])['status'],'completed')
        self.provider.interpret.return_value=intent('why','previous')
        r=self.app.ask({'id':'e'*32,'question':'Why these?'})
        self.assertIn('rotor 0 drives propeller 0',r['answer'])

    def test_speed_change_preserves_last_explained_subject(self):
        self.app.ask(self.request)
        self.provider.interpret.return_value=intent('slow')
        self.app.ask({'id':'d'*32,'question':'Slow it down'})
        self.state['contextToken']='e'*32;self.state['speed']=0.15
        self.transport.receipt.return_value={'status':'executed','message':'Applied','referenceToken':self.state['referenceToken']}
        self.app.get('d'*32)
        self.assertEqual(self.app.memory(self.state)['subject']['id'],'motor_0')

    def test_late_receipt_does_not_attach_to_different_instance(self):
        self.provider.interpret.return_value=intent('isolate_subsystem','subsystem','propulsion')
        self.app.ask(self.request)
        self.state['subject']['instance']='2';self.state['selected']=''
        self.transport.receipt.return_value={'status':'executed','message':'Applied','referenceToken':self.state['referenceToken']}
        self.app.get(self.request['id']);self.assertIsNone(self.app.memory(self.state))

    def test_transfer_failure_waits_for_receipt_and_never_resends(self):
        self.provider.interpret.return_value=intent('play');self.transport.send.side_effect=RuntimeError('private error')
        self.assertEqual(self.app.ask(self.request)['status'],'pending')
        self.now+=41
        self.assertEqual(self.app.get(self.request['id'])['status'],'uncertain')
        self.app.ask(self.request);self.transport.send.assert_called_once()

    def test_pending_action_blocks_second_interpretation(self):
        self.provider.interpret.return_value=intent('play');self.app.ask(self.request)
        with self.assertRaises(CommandError):self.app.ask(dict(self.request,id='d'*32))
        self.provider.interpret.assert_called_once()

    def test_failed_interpreter_does_not_leak_or_retry(self):
        self.provider.interpret.side_effect=RuntimeError('SECRET')
        result=self.app.ask(self.request)
        self.assertEqual(result['status'],'failed');self.assertNotIn('SECRET',result['answer'])
        self.app.ask(self.request);self.provider.interpret.assert_called_once()

    def test_interrupted_record_survives_restart_without_replay(self):
        record={'public':{'id':self.request['id'],'status':'working','answer':''}}
        with self.app.db() as db:db.execute('INSERT INTO turns VALUES (?,?,?,?)',('f'*32,'fp','working',json.dumps(record)))
        again=Conversation(self.path,self.factory,self.transport)
        self.assertEqual(again.get('f'*32)['status'],'uncertain')
        self.provider.interpret.assert_not_called()

    def test_cancel_during_provider_call_prevents_late_action_and_replay(self):
        import threading
        entered,release=threading.Event(),threading.Event()
        def interpret(*_):
            entered.set();self.assertTrue(release.wait(3));return intent('play')
        self.provider.interpret.side_effect=interpret
        results=[];worker=threading.Thread(target=lambda:results.append(self.app.ask(self.request)))
        worker.start();self.assertTrue(entered.wait(3))
        try:
            cancelled=self.app.cancel({'id':self.request['id']})
            self.assertEqual(cancelled['status'],'cancelled')
            self.assertEqual(self.app.get(self.request['id'])['status'],'cancelled')
        finally:release.set();worker.join(3)
        self.assertFalse(worker.is_alive());self.assertEqual(results[0]['status'],'cancelled')
        self.transport.send.assert_not_called();self.assertIsNone(self.app.memory(self.state))
        self.assertEqual(self.app.ask(self.request)['status'],'cancelled')
        self.provider.interpret.assert_called_once()

    def test_cancelled_provider_failure_cannot_overwrite_cancellation(self):
        def interpret(*_):
            self.app.cancel({'id':self.request['id']});raise RuntimeError('provider failure')
        self.provider.interpret.side_effect=interpret
        self.assertEqual(self.app.ask(self.request)['status'],'cancelled')
        self.transport.send.assert_not_called()

    def test_cancel_after_dispatch_is_honest_about_execution(self):
        self.provider.interpret.return_value=intent('play');self.app.ask(self.request)
        result=self.app.cancel({'id':self.request['id']})
        self.assertEqual(result['status'],'pending');self.assertIn('already been dispatched',result['cancelMessage'])
        self.transport.send.assert_called_once()

    def test_late_receipt_after_selection_away_and_back_does_not_revive_context(self):
        self.provider.interpret.return_value=intent('isolate_component','component','motor_0')
        self.app.ask(self.request)
        previous=self.state['referenceToken'];self.state['referenceToken']='e'*32
        self.transport.receipt.return_value={'status':'executed','message':'Applied','referenceToken':previous}
        self.app.get(self.request['id']);self.assertIsNone(self.app.memory(self.state))

    def test_feedback_and_receipt_progress_without_browser_polling(self):
        self.app.feedback=Mock();self.provider.interpret.return_value=intent('play')
        self.app.ask(self.request)
        self.assertEqual([c.args[1]['phase'] for c in self.app.feedback.publish.call_args_list],['working','pending'])
        self.transport.receipt.return_value={'status':'executed','message':'Applied','referenceToken':self.state['referenceToken']}
        self.app.refresh_pending()
        notices=[c.args[1] for c in self.app.feedback.publish.call_args_list]
        self.assertEqual(notices[-1]['phase'],'completed')
        self.assertEqual(notices[-1]['message'],'Motion is playing.')
        self.assertEqual([n['sequence'] for n in notices],sorted(n['sequence'] for n in notices))

    def test_feedback_failure_does_not_break_application_answer(self):
        self.app.feedback=Mock();self.app.feedback.publish.side_effect=RuntimeError('display lost')
        self.assertEqual(self.app.ask(self.request)['status'],'completed')



class InterpreterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.now=PRICE_REVIEWED+3600
        self.ledger=UsageLedger(Path(self.temp.name)/'usage.sqlite3',clock=lambda:self.now)
        self.counter=Mock(return_value=1000);self.sender=Mock(side_effect=self.response)
        self.provider=ExperienceInterpreter(self.ledger,'SECRET',self.counter,self.sender,clock=lambda:self.now)
    def tearDown(self):self.temp.cleanup()
    def response(self,*args):
        self.assertEqual(self.ledger.get('c'*32)['status'],'reserved')
        return {'status':'completed','model':'gpt-6-sol','service_tier':'default','usage':{'input_tokens':1000,'output_tokens':100},
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(intent('play'))}]}]}
    def test_shared_budget_reserved_before_provider_and_settled(self):
        self.assertEqual(self.provider.interpret('c'*32,'play',state(),None),intent('play'))
        row=self.ledger.get('c'*32);self.assertEqual(row['status'],'completed')
        self.assertLessEqual(row['reserved_nanos'],30_000_000)
        body=self.sender.call_args.args[1];self.assertNotIn('tools',body);self.assertFalse(body['store'])
        with self.assertRaises(CommandError):self.provider.interpret('c'*32,'play',state(),None)
        self.sender.assert_called_once()
    def test_model_receives_scoped_knowledge_without_promoting_component_evidence(self):
        s=drone_state()
        self.provider.interpret('c'*32,'What makes this drone fly?',s,None)
        body=self.sender.call_args.args[1]
        payload=json.loads(body['input'][1]['content'])
        self.assertEqual(payload['request'],'What makes this drone fly?')
        self.assertEqual(payload['explanations'][0],propulsion_explanation(s['subject']))
        self.assertEqual(payload['object'],s['subject'])
        self.assertEqual({c['evidence'] for c in payload['object']['components']},{'unsupported'})

    def test_uncertain_usage_no_retry(self):
        self.sender.side_effect=RuntimeError('SECRET')
        with self.assertRaises(CommandError):self.provider.interpret('c'*32,'play',state(),None)
        self.assertEqual(self.ledger.get('c'*32)['status'],'uncertain')
    def test_invalid_model_output_is_billed_but_cannot_execute(self):
        def bad(*args):
            r=self.response();r['output'][0]['content'][0]['text']=json.dumps(intent('delete'));return r
        self.sender.side_effect=bad
        with self.assertRaises(CommandError):self.provider.interpret('c'*32,'delete',state(),None)
        self.assertEqual(self.ledger.get('c'*32)['outcome'],'invalid_response')
    def test_expired_prices_prevent_external_calls(self):
        self.now+=30*86400
        with self.assertRaises(CommandError):self.provider.interpret('c'*32,'play',state(),None)
        self.counter.assert_not_called();self.sender.assert_not_called()


class ConversationHttpTests(unittest.TestCase):
    def test_local_route_auth_and_default_experience(self):
        import threading
        import urllib.request
        import urllib.error
        from types import SimpleNamespace
        from app import Server
        with tempfile.TemporaryDirectory() as folder:
            server=Server(0,SimpleNamespace(root=Path(folder),research=None))
            server.conversation=Mock()
            server.conversation.ask.return_value={'id':'a'*32,'status':'completed','answer':'Authored model'}
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with urllib.request.urlopen(server.origin+'/') as response:self.assertIn(b'Explore the drone.',response.read())
                with urllib.request.urlopen(server.origin+'/objects') as response:self.assertIn(b'Ask. It appears.',response.read())
                with urllib.request.urlopen(server.origin+'/api/conversation-session') as response:self.assertEqual(json.load(response)['token'],server.token)
                body=json.dumps({'id':'a'*32,'question':'What is this?'}).encode()
                headers={'Content-Type':'application/json','Origin':server.origin}
                request=urllib.request.Request(server.origin+'/api/conversation',data=body,headers=headers)
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
                self.assertEqual(error.exception.code,403);server.conversation.ask.assert_not_called()
                headers['X-Oryn-Token']=server.token
                request=urllib.request.Request(server.origin+'/api/conversation',data=body,headers=headers)
                with urllib.request.urlopen(request) as response:self.assertEqual(json.load(response)['status'],'completed')
                server.conversation.ask.assert_called_once()
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
