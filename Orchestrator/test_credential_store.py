"""Offline Keychain contract tests. Never touch the real user Keychain."""
import ctypes as C
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from app import Jobs
from credential_store import MacKeychain, CredentialError, NOT_FOUND, validate_key


class KeychainTests(unittest.TestCase):
    def setUp(self):
        self.store = object.__new__(MacKeychain)
        for name in ('find', 'add', 'modify', 'free', 'release'):
            setattr(self.store, name, Mock(return_value=0))

    def test_missing_is_empty_and_never_creates(self):
        self.store.find.return_value = NOT_FOUND
        self.assertEqual(self.store.load(), '')
        self.store.add.assert_not_called()

    def test_openai_account_never_overwrites_meshy(self):
        self.store.account=b'openai-api-key'
        self.store.find.return_value=NOT_FOUND
        self.store.save('OPENAI_FIXTURE_KEY')
        self.assertEqual(self.store.find.call_args.args[4],b'openai-api-key')
        self.assertEqual(self.store.add.call_args.args[4],b'openai-api-key')

    def test_load_copies_then_frees_password_buffer(self):
        value = b'fixture-credential-only'
        buffer = C.create_string_buffer(value)
        def find(*args):
            C.cast(args[5], C.POINTER(C.c_uint32))[0] = len(value)
            C.cast(args[6], C.POINTER(C.c_void_p))[0] = C.addressof(buffer)
            return 0
        self.store.find.side_effect = find
        self.assertEqual(self.store.load(), value.decode())
        self.store.free.assert_called_once()

    def test_denied_access_is_not_treated_as_missing(self):
        self.store.find.return_value = -25293
        with self.assertRaises(CredentialError): self.store.load()
        with self.assertRaises(CredentialError): self.store.save('fixture-credential-only')
        self.store.add.assert_not_called()

    def test_new_item_adds_and_existing_item_updates_releases(self):
        self.store.find.return_value = NOT_FOUND
        self.store.save('fixture-credential-only')
        self.store.add.assert_called_once(); self.store.modify.assert_not_called()
        def find(*args):
            C.cast(args[7], C.POINTER(C.c_void_p))[0] = 123
            return 0
        self.store.find.side_effect = find
        self.store.save('replacement-fixture-only')
        self.store.modify.assert_called_once(); self.store.release.assert_called_once()

    def test_add_failure_has_no_plaintext_fallback(self):
        self.store.find.return_value = NOT_FOUND
        self.store.add.return_value = -25293
        with self.assertRaises(CredentialError): self.store.save('fixture-credential-only')

    def test_validate_rejects_control_characters(self):
        for value in ('short', 'fixture-key\n', 'fixture-key\r', 'fixture-key\0', None):
            with self.subTest(value=value), self.assertRaises(CredentialError): validate_key(value)

    def test_jobs_restore_and_save_without_serializing_key(self):
        store = Mock(); store.load.return_value = 'fixture-credential-only'
        with tempfile.TemporaryDirectory() as root:
            jobs = Jobs(Path(root)/'jobs', Path(root)/'unused', credential_store=store)
            self.assertTrue(jobs.state()['configured'])
            self.assertEqual(jobs.state()['keyStorage'], 'keychain')
            self.assertNotIn('fixture-credential-only', str(jobs.state()))
            result = jobs.configure_key('replacement-fixture-only')
            store.save.assert_called_once_with('replacement-fixture-only')
            self.assertEqual(result, {'configured':True, 'keyStorage':'keychain'})
            # Workflow metadata now exists before the first request, but no keys
            # or alternate credential files may be serialized alongside it.
            files = list((Path(root)/'jobs').iterdir())
            self.assertEqual([p.name for p in files], ['workflows.sqlite3'])
            for path in files:
                self.assertNotIn(b'fixture-credential-only', path.read_bytes())
                self.assertNotIn(b'replacement-fixture-only', path.read_bytes())

    def test_save_failure_preserves_existing_connection(self):
        store = Mock(); store.load.return_value = 'existing-fixture-only'
        store.save.side_effect = CredentialError('Keychain locked')
        with tempfile.TemporaryDirectory() as root:
            jobs = Jobs(Path(root)/'jobs', Path(root)/'unused', credential_store=store)
            with self.assertRaises(CredentialError): jobs.configure_key('replacement-fixture-only')
            self.assertEqual(jobs.key, 'existing-fixture-only')

    def test_startup_denial_is_visible_without_leaking_or_crashing(self):
        store = Mock(); store.load.side_effect = CredentialError('Keychain locked')
        with tempfile.TemporaryDirectory() as root:
            jobs = Jobs(Path(root)/'jobs', Path(root)/'unused', credential_store=store)
            self.assertFalse(jobs.state()['configured'])
            self.assertEqual(jobs.state()['credentialError'], 'Keychain locked')


if __name__ == '__main__': unittest.main()
