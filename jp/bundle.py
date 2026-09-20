"""Offline client bundle generation; never changes a deployed subscription."""
import copy
from urllib.parse import urlsplit


def bundle(configs, mode='manual', health_url='https://www.gstatic.com/generate_204'):
    if mode not in ('manual', 'fallback', 'url-test') or not configs:
        raise ValueError('Select a mode and at least one single-protocol client')
    url = urlsplit(health_url)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError('Health URL must be credential-free HTTPS')
    nodes = []
    for name, cfg in configs.items():
        if len(cfg.get('proxies', [])) != 1 or cfg.get('rules') != ['MATCH,node']:
            raise ValueError('Expected an unmodified single-protocol client')
        node = copy.deepcopy(cfg['proxies'][0])
        if node.get('skip-cert-verify') or name in ('DIRECT', 'REJECT', 'Relay', 'Auto'):
            raise ValueError('Unsafe client or reserved node name')
        node['name'] = name
        nodes.append(node)
    names = [node['name'] for node in nodes]
    groups = [{'name': 'Relay', 'type': 'select', 'proxies': names}]
    if mode != 'manual':
        auto = {'name': 'Auto', 'type': mode, 'proxies': names,
                'url': health_url, 'interval': 120, 'lazy': False}
        if mode == 'url-test':
            auto['tolerance'] = 50
        groups = [{'name': 'Relay', 'type': 'select', 'proxies': ['Auto'] + names}, auto]
    return {'mixed-port': 17890, 'allow-lan': False, 'bind-address': '127.0.0.1',
            'mode': 'rule', 'log-level': 'silent', 'ipv6': False,
            'proxies': nodes, 'proxy-groups': groups, 'rules': ['MATCH,Relay']}
