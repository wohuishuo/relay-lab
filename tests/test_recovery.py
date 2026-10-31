import copy
import unittest

from jp.client_policy import mobile_profile, stable_profile
from jp.recovery import GATE, GRPC_RECOVERY, TCP_TARGETS, repair_profile


def source():
    kinds = ['vless', 'anytls', 'trojan', 'ss', 'vless', 'vless']
    nodes = [dict(name=name, type=kind, server='node.test', port=1234) for name, kind in zip(TCP_TARGETS, kinds)]
    nodes += [dict(name='JP-TUIC', type='tuic'), dict(name='JP-HY2', type='hysteria2'),
              dict(name='JP-GRPC-DIRECT', type='vless', network='grpc'),
              {'name': 'JP-GRPC', 'type': 'vless', 'network': 'grpc', 'dialer-proxy': 'JP-HY2'}]
    return stable_profile({'proxies': nodes}, direct_domains=['qq.com'])


class RecoveryTests(unittest.TestCase):
    def test_working_nodes_and_native_auto_semantics(self):
        old = source()
        before = copy.deepcopy(old)
        new = repair_profile(old)
        nodes = {n['name']: n for n in new['proxies']}
        originals = {n['name']: n for n in old['proxies']}
        groups = {g['name']: g for g in new['proxy-groups']}
        self.assertEqual(old, before)
        for name in ('JP-TUIC', 'JP-HY2', 'JP-GRPC', 'JP-GRPC-DIRECT'):
            self.assertEqual(nodes[name], originals[name])
        for a,b in zip(old['proxy-groups'][1]['proxies'],groups['JP-AUTO']['proxies'],strict=True):
            self.assertEqual(originals[a],dict(nodes[b],name=a))
        for name in TCP_TARGETS:
            self.assertEqual(nodes[name],dict(originals[name],**{'dialer-proxy':GATE}))
        self.assertEqual(groups[GATE]['proxies'],['JP-TUIC','JP-HY2'])
        self.assertEqual(nodes[GRPC_RECOVERY]['dialer-proxy'],GATE)
        self.assertEqual(new['dns'],old['dns'])
        self.assertEqual(new['rules'],old['rules'])

    def test_exporters_can_consume_repaired_profile_without_chains_multiplying(self):
        old=source();new=repair_profile(old)
        self.assertEqual(stable_profile(new,direct_domains=['qq.com']),old)
        self.assertEqual(mobile_profile(new,candidates=['JP-TUIC','JP-HY2']),mobile_profile(old,candidates=['JP-TUIC','JP-HY2']))
        next(n for n in new['proxies'] if n['name']=='JP-SS')['port']=4321
        with self.assertRaises(ValueError):stable_profile(new)
