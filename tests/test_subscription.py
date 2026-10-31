import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jp.certificates import generate_test_certs
from jp.subscription import prepare, fetch, deploy, check, rotate, stop


class SubscriptionRouteTests(unittest.TestCase):
    def test_rotation_revokes_all_profiles_sharing_secret_parent(self):
        from jp import subscription
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            dest = state / 'subscription'
            (dest / 'runtime').mkdir(parents=True)
            (dest / 'url.txt').write_text('https://node.test:2087/sub/test-old/config.yaml\n')
            config = '\n'.join('path /sub/test-old/' + name for name in ('config.yaml', 'legacy.yaml', 'mobile.yaml'))
            (dest / 'runtime/Caddyfile').write_text(config + '\nrewrite * /mobile.yaml\n')
            with patch.object(subscription, 'stop'), patch.object(subscription, 'deploy'), \
                    patch.object(subscription, 'runtime_permissions'), \
                    patch.object(subscription.secrets, 'token_urlsafe', return_value='test-new'):
                rotate(state)
            actual = (dest / 'runtime/Caddyfile').read_text()
            self.assertNotIn('/sub/test-old/', actual)
            for name in ('config.yaml', 'legacy.yaml', 'mobile.yaml'):
                self.assertIn('/sub/test-new/' + name, actual)
            self.assertIn('rewrite * /mobile.yaml', actual)


@unittest.skipUnless(os.environ.get('JP_DOCKER_TEST') == '1', 'Docker regression is opt-in')
class SubscriptionTests(unittest.TestCase):
    def test_real_https_authentication_restart_and_no_directory_disclosure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / 'state'
            certs = state / 'certs/live'
            generate_test_certs(certs)
            client = root / 'client.yaml'
            client.write_text(json.dumps({'proxies': [{'name': 'sample', 'type': 'trojan',
                'server': 'node.test', 'port': 443, 'password': 'test-only', 'skip-cert-verify': False}],
                'rules': ['MATCH,sample']}), encoding='utf-8')
            prepare(state, client, 'node.test', port=32087)
            try:
                deploy(state, ca=certs / 'ca.crt')
                check(state, ca=certs / 'ca.crt')
                url = (state / 'subscription/url.txt').read_text().strip()
                status, body = fetch(url, ca=certs / 'ca.crt', resolve='127.0.0.1')
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body), json.loads(client.read_text()))
                with self.assertRaises(RuntimeError):
                    fetch(url, resolve='127.0.0.1')  # untrusted CA MUST fail
                with self.assertRaises(RuntimeError):
                    fetch(url.replace('node.test', 'wrong.test'), ca=certs / 'ca.crt', resolve='127.0.0.1')
                for suffix in ['/', '/config.yaml', '/Caddyfile', '/sub/wrong/config.yaml']:
                    status, body = fetch('https://node.test:32087' + suffix,
                        ca=certs / 'ca.crt', resolve='127.0.0.1')
                    self.assertEqual(status, 404)
                    self.assertNotIn(b'test-only', body)
                status, _ = fetch(url, ca=certs / 'ca.crt', resolve='127.0.0.1', method='POST')
                self.assertEqual(status, 404)
                stop(state)
                deploy(state, ca=certs / 'ca.crt')
                check(state, ca=certs / 'ca.crt')
                rotate(state, ca=certs / 'ca.crt')
                status, _ = fetch(url, ca=certs / 'ca.crt', resolve='127.0.0.1')
                self.assertEqual(status, 404)
                check(state, ca=certs / 'ca.crt')
            finally:
                stop(state, remove=True)
