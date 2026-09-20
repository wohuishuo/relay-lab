import tempfile
import os
import unittest
from pathlib import Path
from jp.certificates import generate_test_certs, check_pair


class CertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name)
        generate_test_certs(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_valid_chain_and_hostname(self):
        check_pair(self.path / 'server.crt', self.path / 'server.key', 'node.test', ca=self.path / 'ca.crt')

    def test_wrong_domain_rejected(self):
        with self.assertRaises((RuntimeError, ValueError)):
            check_pair(self.path / 'server.crt', self.path / 'server.key', 'wrong.test')

    def test_wrong_key_rejected(self):
        with self.assertRaises((RuntimeError, ValueError)):
            check_pair(self.path / 'server.crt', self.path / 'wrong-ca.key', 'node.test')

    def test_untrusted_chain_rejected(self):
        with self.assertRaises((RuntimeError, ValueError)):
            check_pair(self.path / 'server.crt', self.path / 'server.key', 'node.test', ca=self.path / 'wrong-ca.crt')

    @unittest.skipUnless(os.environ.get('JP_LEGO'), 'Set JP_LEGO for the pinned CLI syntax check')
    def test_pinned_lego_accepts_real_command_flags_without_network(self):
        from jp.certificates import acme_command
        from jp.common import run
        args = acme_command(os.environ['JP_LEGO'], self.path / 'acme', 'node.example.com', 'owner@example.com', 'cloudflare', staging=True)
        result = run(args + ['--help'])
        self.assertIn('renew-days', result.stdout)
