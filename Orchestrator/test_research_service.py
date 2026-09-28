"""Integrated application worker tests: fixtures only, no live I/O."""
import json
from pathlib import Path
from unittest.mock import Mock
import unittest

from app import Jobs
from credential_store import CredentialError
from research_service import ResearchService
import test_generation as fixtures
from test_generation import FakeProvider
from test_investigation import source, synthesis
from usage_ledger import UsageLedger


class ResearchServiceTests(unittest.TestCase):
    setUp=fixtures.GenerationTests.setUp
    tearDown=fixtures.GenerationTests.tearDown
    wait=fixtures.GenerationTests.wait

    def attach(self, key=''):
        self.sources=Mock(); self.sources.retrieve.return_value=[source()]
        self.cognitive=Mock(); self.cognitive.investigate.return_value=synthesis()
        self.credentials=Mock(); self.credentials.load.return_value=key
        service=ResearchService(self.jobs,self.credentials,
            ledger=UsageLedger(self.root/'usage.sqlite3'),retrieval=self.sources,
            cognitive_factory=lambda *args:self.cognitive)
        self.jobs.research=service
        return service

    def request(self):
        self.jobs.key='MESHY_FIXTURE'
        self.jobs.request_object({'request_id':'a'*32,'prompt':'V8 engine'})
        self.wait()

    def test_request_delivers_without_waiting_for_research(self):
        service=self.attach('OPENAI_FIXTURE'); self.request()
        self.assertEqual(self.jobs.jobs['a'*32]['status'],'loaded_on_quest')
        self.sources.retrieve.assert_not_called()
        self.assertEqual(self.jobs.state()['jobs'][0]['research']['status'],'queued')
        service.engine.run_next()
        self.assertEqual(self.jobs.state()['jobs'][0]['research']['status'],'reference_notes_ready')
        self.assertEqual(self.transport.calls,1)

    def test_missing_key_retains_sources_save_key_resumes_only_synthesis(self):
        service=self.attach(); self.request()
        service.engine.run_next()
        self.assertEqual(self.jobs.state()['jobs'][0]['research']['status'],'awaiting_cognitive_provider')
        self.cognitive.investigate.assert_not_called()
        service.configure_key('OPENAI_FIXTURE_KEY')
        self.credentials.save.assert_called_once_with('OPENAI_FIXTURE_KEY')
        service.engine.run_next()
        self.sources.retrieve.assert_called_once(); self.cognitive.investigate.assert_called_once()
        self.assertNotIn('OPENAI_FIXTURE_KEY',json.dumps(self.jobs.state()))
        self.assertNotIn(b'OPENAI_FIXTURE_KEY',(self.jobs.root/'workflows.sqlite3').read_bytes())

    def test_keychain_save_failure_preserves_existing_connection(self):
        service=self.attach('OLD_FIXTURE_KEY')
        self.credentials.save.side_effect=CredentialError('Keychain unavailable')
        with self.assertRaises(CredentialError): service.configure_key('NEW_FIXTURE_KEY')
        self.assertEqual(service.key,'OLD_FIXTURE_KEY')

    def test_research_requests_are_idempotent_and_do_not_send_models(self):
        service=self.attach('OPENAI_FIXTURE'); self.request()
        before=self.jobs.jobs['a'*32]['updated']
        first=service.enqueue_job('a'*32); service.engine.run_next()
        second=service.enqueue_job('a'*32)
        self.assertEqual(first['id'],second['id'])
        self.assertIsNone(service.engine.run_next())
        self.assertEqual(self.transport.calls,1)
        self.assertEqual(self.jobs.jobs['a'*32]['updated'],before)
        self.assertEqual(FakeProvider.calls,1)

    def test_restart_backfill_never_enqueues_new_research(self):
        self.request()
        restarted=Jobs(self.jobs.root,self.fixture,provider=FakeProvider,transport=self.transport)
        self.jobs=restarted; service=self.attach()
        self.assertIsNone(service.engine.run_next())
        self.sources.retrieve.assert_not_called()

    def test_research_failure_cannot_invalidate_model(self):
        service=self.attach('OPENAI_FIXTURE'); self.request()
        self.sources.retrieve.side_effect=RuntimeError('PRIVATE_ERROR')
        service.engine.run_next()
        state=self.jobs.state()
        self.assertEqual(state['jobs'][0]['status'],'loaded_on_quest')
        self.assertEqual(state['jobs'][0]['research']['status'],'failed')
        self.assertNotIn('PRIVATE_ERROR',json.dumps(state))

    def test_saved_match_reuses_research_across_case_and_whitespace(self):
        service=self.attach('OPENAI_FIXTURE'); self.request()
        service.engine.run_next()
        first=self.jobs.jobs['a'*32]['research_id']
        self.jobs.request_object({'request_id':'b'*32,'prompt':'Show me V8   ENGINE'}); self.wait()
        self.assertEqual(self.jobs.jobs['b'*32]['research_id'],first)
        self.assertIsNone(service.engine.run_next())
        self.cognitive.investigate.assert_called_once()
        self.assertEqual(FakeProvider.calls,1)


if __name__=='__main__': unittest.main()
