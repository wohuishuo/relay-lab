"""Small client policy without remote rule downloads or changes to node credentials."""
import copy
import re


BALANCED_DOMAINS = (
    'qq.com', 'wechat.com', 'alipay.com', 'taobao.com', 'tmall.com',
    'jd.com', 'baidu.com', 'bilibili.com', 'douyin.com', 'amap.com',
    '163.com', '126.com',
)
RESERVED = {'DIRECT', 'REJECT', 'GLOBAL', 'JP-STABLE', 'JP-AUTO', 'JP-MOBILE', 'JP-MOBILE-AUTO'}
DIRECT_DNS = ['https://223.5.5.5/dns-query#DIRECT', 'https://223.6.6.6/dns-query#DIRECT']


def stable_profile(source, *, direct_domains=()):
    nodes = copy.deepcopy(source.get('proxies', []))
    names = [n.get('name') for n in nodes]
    if not nodes or any(not isinstance(n, str) or not n or ',' in n or '\n' in n for n in names):
        raise ValueError('Every node needs a unique, unambiguous name')
    if len(set(names)) != len(names) or RESERVED.intersection(names):
        raise ValueError('Duplicate or reserved node name')
    by_name = {n['name']: n for n in nodes}
    for node in nodes:
        if node.get('skip-cert-verify'):
            raise ValueError('Certificate verification must remain enabled')
        seen = set()
        cursor = node['name']
        while cursor in by_name:
            if cursor in seen:
                raise ValueError('Cyclic dialer-proxy chain')
            seen.add(cursor)
            cursor = by_name[cursor].get('dialer-proxy')
        if cursor not in (None, '', 'DIRECT'):
            raise ValueError('Missing dialer-proxy dependency')
    domains = []
    for domain in direct_domains:
        domain = domain.lower().rstrip('.')
        if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', domain):
            raise ValueError('Invalid direct domain')
        if domain not in domains:
            domains.append(domain)
    priority = {'hysteria2': 0, 'tuic': 1, 'ss': 2, 'trojan': 3, 'anytls': 4, 'vless': 5}
    eligible = [n for n in nodes if n['type'] in priority and not n.get('dialer-proxy')
                and (n['type'] != 'vless' or n.get('network', 'tcp') in ('tcp', 'raw'))]
    if not eligible:
        raise ValueError('No independent node is available for automatic fallback')
    auto_names = [n['name'] for n in sorted(eligible, key=lambda n: priority[n['type']])]
    policies = {'+.lan': ['system'], '+.local': ['system'], 'localhost': ['system']}
    policies.update({'+.' + domain: list(DIRECT_DNS) for domain in domains})
    rules = ['DOMAIN,localhost,DIRECT', 'DOMAIN-SUFFIX,lan,DIRECT', 'DOMAIN-SUFFIX,local,DIRECT']
    rules += ['DOMAIN-SUFFIX,' + d + ',DIRECT' for d in domains]
    rules += ['IP-CIDR,' + subnet + ',DIRECT,no-resolve' for subnet in (
        '127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16')]
    rules += ['MATCH,JP-STABLE']
    return {
        'mixed-port': 17890, 'allow-lan': False, 'bind-address': '127.0.0.1',
        'mode': 'rule', 'log-level': 'silent', 'ipv6': False,
        'proxies': nodes,
        'proxy-groups': [
            {'name': 'JP-STABLE', 'type': 'select', 'proxies': ['JP-AUTO'] + names},
            {'name': 'JP-AUTO', 'type': 'fallback', 'proxies': auto_names,
             'url': 'https://www.gstatic.com/generate_204', 'interval': 30,
             'timeout': 6000, 'lazy': False, 'max-failed-times': 2},
        ],
        'dns': {
            'enable': True, 'listen': '127.0.0.1:1053', 'ipv6': False,
            'enhanced-mode': 'fake-ip', 'fake-ip-range': '198.18.0.1/16',
            'fake-ip-filter': ['*.lan', '*.local', 'localhost'],
            'cache-algorithm': 'lru', 'prefer-h3': False, 'respect-rules': True,
            'default-nameserver': list(DIRECT_DNS),
            'proxy-server-nameserver': list(DIRECT_DNS),
            'direct-nameserver': list(DIRECT_DNS),
            'nameserver': ['https://1.1.1.1/dns-query#JP-AUTO', 'https://8.8.8.8/dns-query#JP-AUTO'],
            'nameserver-policy': policies,
        },
        'rules': rules,
    }


def mobile_profile(source, *, candidates, direct_domains=()):
    """Keep explicitly accepted paths only; the caller must test them externally.

    This generates a separate profile and never edits the original. A successful
    parse is not evidence that a candidate works from the eventual phone.
    """
    result = stable_profile(source, direct_domains=direct_domains)
    by_name = {node['name']: node for node in result['proxies']}
    names = list(candidates)
    if not names or len(set(names)) != len(names) or any(name not in by_name for name in names):
        raise ValueError('Supply unique names of externally tested candidates')
    if any(by_name[name].get('dialer-proxy') for name in names):
        raise ValueError('Dependent chains are not independent mobile candidates')
    result['proxies'] = [by_name[name] for name in names]
    result['proxy-groups'] = [
        {'name': 'JP-MOBILE', 'type': 'select', 'proxies': ['JP-MOBILE-AUTO'] + names},
        {'name': 'JP-MOBILE-AUTO', 'type': 'url-test', 'proxies': names,
         'url': 'https://www.gstatic.com/generate_204', 'expected-status': '204',
         'interval': 30, 'timeout': 8000, 'tolerance': 150,
         'lazy': False, 'max-failed-times': 2},
        # Accidental global mode must not silently start on DIRECT. Rule mode
        # remains necessary for the explicit domestic/LAN direct policy.
        {'name': 'GLOBAL', 'type': 'select', 'proxies': ['JP-MOBILE']},
    ]
    result['rules'][-1] = 'MATCH,JP-MOBILE'
    dns = result['dns']
    dns['nameserver'] = [resolver.replace('#JP-AUTO', '#JP-MOBILE-AUTO') for resolver in dns['nameserver']]
    # Explicit direct domains receive real answers, avoiding synthetic addresses
    # in applications that embed resolved addresses in their own messages.
    dns['fake-ip-filter'] += [key for key in dns['nameserver-policy'] if key.startswith('+.') and key not in ('+.lan', '+.local')]
    return result
