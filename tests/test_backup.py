import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from jp.operations import backup, restore


class BackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.age = os.environ.get('JP_AGE')
        cls.keygen = os.environ.get('JP_AGE_KEYGEN')
        if not cls.age or not cls.keygen:
            raise unittest.SkipTest('Set JP_AGE and JP_AGE_KEYGEN to verified tools for real crypto round-trip')

    def test_round_trip_and_wrong_key_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / 'state'
            (state / 'releases/a').mkdir(parents=True)
            (state / 'releases/a/secrets.json').write_text('{"test":"not-a-production-secret"}')
            (state / 'subscription').mkdir()
            (state / 'subscription/url.txt').write_text('https://test.invalid/private-test-token')
            # Minimal fixture uses a file-only release directory; runtime ownership is Linux-only.
            identity = root / 'identity.txt'
            subprocess.run([self.keygen, '-o', str(identity)], check=True, capture_output=True)
            recipient = subprocess.run([self.keygen, '-y', str(identity)], check=True, capture_output=True, text=True).stdout.strip()
            encrypted = root / 'backup.age'
            digest = backup(state, recipient, encrypted, self.age)
            self.assertEqual(digest, hashlib.sha256(encrypted.read_bytes()).hexdigest())
            self.assertNotIn(b'not-a-production-secret', encrypted.read_bytes())
            # Provide a valid runtime directory so Linux permission restoration is also exercised.
            (state / 'releases/a/runtime').mkdir()
            (state / 'releases/a/runtime/server.yaml').write_text('{}')
            encrypted2 = root / 'backup2.age'
            backup(state, recipient, encrypted2, self.age)
            restore(encrypted2, identity, root / 'restored', self.age)
            self.assertEqual((root / 'restored/releases/a/secrets.json').read_text(), '{"test":"not-a-production-secret"}')
            self.assertEqual((root / 'restored/subscription/url.txt').read_text(), 'https://test.invalid/private-test-token')
            wrong = root / 'wrong.txt'
            subprocess.run([self.keygen, '-o', str(wrong)], check=True, capture_output=True)
            with self.assertRaises(RuntimeError):
                restore(encrypted2, wrong, root / 'wrong-restore', self.age)
            self.assertFalse((root / 'wrong-restore').exists())
