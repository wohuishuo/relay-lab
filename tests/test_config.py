import importlib.util
import tempfile
import unittest
from pathlib import Path


class ConfigTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('jp.config'), 'configuration API must exist')
        from jp import config
        return config

    def test_untrusted_inputs_rejected_before_render(self):
        c = self.api()
        for domain in ['example.com\nBAD', '../private', 'https://node.example.com', '*.example.com', '']:
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                c.validate_domain(domain)
        for protocols in [[], ['ssh'], ['hy2', 'hy2']]:
            with self.subTest(protocols=protocols), self.assertRaises(ValueError):
                c.validate_protocols(protocols)

    def test_production_never_exposes_unselected_ports_or_api(self):
        c = self.api()
        secrets = c.example_secrets()
        cfg = c.server_config(['reality', 'hy2'], secrets, 'node.example.com', 'www.example.org:443', 'www.example.org')
        self.assertNotIn('external-controller', cfg)
        self.assertEqual(len(cfg['listeners']), 2)
        self.assertEqual(c.port_bindings(['reality', 'hy2']), ['0.0.0.0:443:14443/tcp', '0.0.0.0:443:14443/udp'])
        self.assertIn('IP-CIDR,169.254.0.0/16,REJECT', cfg['rules'])
        self.assertIn('IP-CIDR6,fc00::/7,REJECT', cfg['rules'])

    def test_tls_clients_verify_and_single_protocol_cannot_fallback(self):
        c = self.api()
        for protocol in c.PROTOCOLS:
            with self.subTest(protocol=protocol):
                cfg = c.client_config(protocol, c.example_secrets(), 'node.example.com', 'node.example.com', 'www.example.org')
                self.assertEqual(cfg['rules'], ['MATCH,node'])
                self.assertEqual(len(cfg['proxies']), 1)
                self.assertNotIn('proxy-groups', cfg)
                self.assertFalse(cfg['proxies'][0].get('skip-cert-verify', False))
                self.assertEqual(cfg['bind-address'], '127.0.0.1')

    def test_image_must_be_upstream_digest(self):
        c = self.api()
        for image in ['metacubex/mihomo:latest', 'evil/mihomo@sha256:' + 'a'*64, 'metacubex/mihomo@sha256:123']:
            with self.assertRaises(ValueError):
                c.validate_image(image)
        c.validate_image('docker.io/metacubex/mihomo@sha256:' + 'a'*64)

    def test_state_inside_repository_rejected(self):
        c = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                c.validate_state(root / 'private', root)
            c.validate_state(root.parent / (root.name + '-state'), root)


if __name__ == '__main__':
    unittest.main()
