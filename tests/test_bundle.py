import unittest
from jp.bundle import bundle
from jp.config import client_config, example_secrets


class BundleTests(unittest.TestCase):
    def config(self):
        return client_config('hy2', example_secrets(), 'node.example.com', 'node.example.com', 'www.example.org')

    def test_no_direct_fallback_or_public_api(self):
        for mode in ('manual', 'fallback', 'url-test'):
            result = bundle({'hy2': self.config()}, mode)
            self.assertEqual(result['rules'], ['MATCH,Relay'])
            self.assertFalse(result['allow-lan'])
            self.assertNotIn('external-controller', result)
            self.assertFalse(result['proxies'][0]['skip-cert-verify'])
            for group in result['proxy-groups']:
                self.assertNotIn('DIRECT', group['proxies'])

    def test_rejects_insecure_or_ambiguous_inputs(self):
        cfg = self.config()
        cfg['proxies'][0]['skip-cert-verify'] = True
        with self.assertRaises(ValueError):
            bundle({'hy2': cfg})
        with self.assertRaises(ValueError):
            bundle({'hy2': self.config()}, 'fallback', 'https://user:pass@example.com/')
        with self.assertRaises(ValueError):
            bundle({'DIRECT': self.config()})
