import copy
import unittest


class ClientPolicyTests(unittest.TestCase):
    def source(self):
        return {
            'proxies': [
                {'name': 'tcp', 'type': 'vless', 'server': '203.0.113.7', 'port': 443,
                 'uuid': '00000000-0000-4000-8000-000000000001', 'network': 'tcp', 'tls': True},
                {'name': 'quic', 'type': 'hysteria2', 'server': '203.0.113.7',
                 'port': 443, 'password': 'example-only'},
                {'name': 'grpc', 'type': 'vless', 'server': '203.0.113.7', 'port': 12443,
                 'uuid': '00000000-0000-4000-8000-000000000001', 'network': 'grpc',
                 'dialer-proxy': 'quic', 'tls': True},
            ]
        }

    def build(self, source, **kw):
        from jp import client_policy
        return client_policy.stable_profile(source, **kw)

    def test_preserves_credentials_and_chain_without_mutating_source(self):
        source = self.source()
        before = copy.deepcopy(source)
        result = self.build(source)
        self.assertEqual(source, before)
        self.assertEqual(result['proxies'], before['proxies'])
        auto = next(g for g in result['proxy-groups'] if g['name'] == 'JP-AUTO')
        self.assertEqual(auto['proxies'], ['quic', 'tcp'])
        self.assertNotIn('DIRECT', auto['proxies'])
        self.assertEqual(result['rules'][-1], 'MATCH,JP-STABLE')

    def test_unknown_dns_uses_proxy_and_direct_exceptions_are_explicit(self):
        result = self.build(self.source(), direct_domains=['qq.com'])
        dns = result['dns']
        self.assertTrue(dns['enable'])
        self.assertTrue(all(x.endswith('#JP-AUTO') for x in dns['nameserver']))
        self.assertNotIn('fallback', dns)
        self.assertIn('+.qq.com', dns['nameserver-policy'])
        self.assertNotIn('+.cn', dns['nameserver-policy'])
        self.assertIn('DOMAIN-SUFFIX,qq.com,DIRECT', result['rules'])
        self.assertFalse(result['allow-lan'])
        self.assertNotIn('external-controller', result)
        self.assertNotIn('tun', result)

    def test_rejects_insecure_or_cyclic_nodes_and_rule_injection(self):
        source = self.source()
        source['proxies'][0]['skip-cert-verify'] = True
        with self.assertRaises(ValueError):
            self.build(source)
        source = self.source()
        source['proxies'][1]['dialer-proxy'] = 'grpc'
        with self.assertRaises(ValueError):
            self.build(source)
        with self.assertRaises(ValueError):
            self.build(self.source(), direct_domains=['example.com,REJECT'])
        source = self.source()
        source['proxies'][0]['name'] = 'JP-AUTO'
        with self.assertRaises(ValueError):
            self.build(source)

    def test_client_does_not_direct_bypass_all_traffic_to_node_ip(self):
        result = self.build(self.source())
        self.assertFalse(any('203.0.113.7' in rule for rule in result['rules']))

    def test_mobile_only_uses_explicit_independent_candidates(self):
        from jp.client_policy import mobile_profile
        source = self.source()
        source['proxies'].append({'name': 'second', 'type': 'tuic',
                                 'server': '203.0.113.7', 'port': 8443,
                                 'uuid': '00000000-0000-4000-8000-000000000002',
                                 'password': 'example-only'})
        before = copy.deepcopy(source)
        result = mobile_profile(source, candidates=['second', 'quic'], direct_domains=['qq.com'])
        self.assertEqual(source, before)
        self.assertEqual(result['proxies'], [before['proxies'][3], before['proxies'][1]])
        groups = {g['name']: g for g in result['proxy-groups']}
        self.assertEqual(groups['JP-MOBILE-AUTO']['proxies'], ['second', 'quic'])
        self.assertEqual(groups['JP-MOBILE']['proxies'][0], 'JP-MOBILE-AUTO')
        self.assertEqual(groups['GLOBAL']['proxies'], ['JP-MOBILE'])
        self.assertEqual(result['rules'][-1], 'MATCH,JP-MOBILE')
        self.assertFalse(any('DIRECT' in g['proxies'] for g in groups.values()))
        self.assertTrue(all(x.endswith('#JP-MOBILE-AUTO') for x in result['dns']['nameserver']))
        self.assertNotIn('proxy-providers', result)
        self.assertNotIn('tun', result)
        self.assertIn('+.qq.com', result['dns']['fake-ip-filter'])

    def test_mobile_rejects_missing_or_dependent_candidates(self):
        from jp.client_policy import mobile_profile
        for candidates in ([], ['missing'], ['quic', 'quic'], ['grpc']):
            with self.subTest(candidates=candidates), self.assertRaises(ValueError):
                mobile_profile(self.source(), candidates=candidates)

    def test_reserved_mobile_names_cannot_be_node_names(self):
        for name in ['GLOBAL', 'JP-MOBILE', 'JP-MOBILE-AUTO']:
            source = self.source()
            source['proxies'][0]['name'] = name
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.build(source)


if __name__ == '__main__':
    unittest.main()
