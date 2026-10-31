"""Repair selected first hops while preserving the existing automatic policy."""
from copy import deepcopy

GATE = 'JP-REPAIR-ENTRY'
TCP_TARGETS = ('JP-REALITY', 'JP-ANYTLS', 'JP-TROJAN', 'JP-SS', 'JP-XHTTP', 'JP-WS')
GRPC_RECOVERY = 'JP-GRPC-RECOVERED'


def native_nodes(source):
    """Read either an original profile or the native controls in our repaired one."""
    nodes = source.get('proxies', [])
    if not any(g.get('name') == GATE for g in source.get('proxy-groups', [])):
        return nodes
    by_name = {n['name']: n for n in nodes}
    if len(by_name) != len(nodes):
        raise ValueError('Ambiguous recovery profile')
    controls = {name + '-DIRECT' for name in TCP_TARGETS} | {GRPC_RECOVERY}
    restored = []
    for node in nodes:
        name = node['name']
        if name in controls:
            continue
        if name in TCP_TARGETS:
            original = dict(by_name[name + '-DIRECT'], name=name)
            if node != dict(original, **{'dialer-proxy': GATE}):
                raise ValueError('Recovered node and native control differ')
            restored.append(original)
        else:
            restored.append(node)
    return restored


def repair_profile(source):
    profile = deepcopy(source)
    nodes = profile['proxies']
    groups = profile['proxy-groups']
    by_name = {n['name']: n for n in nodes}
    by_group = {g['name']: g for g in groups}
    names = set(by_name) | set(by_group)
    added = {GATE, GRPC_RECOVERY, *(n + '-DIRECT' for n in TCP_TARGETS)}
    if names & added or len(names) != len(nodes) + len(groups):
        raise ValueError('Duplicate or reserved recovery name')
    for name, kind in [('JP-TUIC', 'tuic'), ('JP-HY2', 'hysteria2')]:
        entry = by_name[name]
        if entry['type'] != kind or entry.get('dialer-proxy') or entry.get('skip-cert-verify'):
            raise ValueError('Invalid independent first hop')
    auto, manual = by_group['JP-AUTO'], by_group['JP-STABLE']
    if auto['type'] != 'fallback' or manual['type'] != 'select':
        raise ValueError('Unexpected existing policy; do not overwrite')
    for name in (*TCP_TARGETS, 'JP-GRPC-DIRECT'):
        node = by_name[name]
        if node.get('dialer-proxy') or node.get('skip-cert-verify') or (node.get('plugin-opts') or {}).get('skip-cert-verify'):
            raise ValueError('Expected an independently verified original node')
        if name == 'JP-GRPC-DIRECT':
            nodes.append(dict(deepcopy(node), name=GRPC_RECOVERY, **{'dialer-proxy': GATE}))
            manual['proxies'].append(GRPC_RECOVERY)
            continue
        control = name + '-DIRECT'
        nodes.append(dict(deepcopy(node), name=control))
        node['dialer-proxy'] = GATE
        manual['proxies'].append(control)
        # Auto continues to probe/use the exact native transports it used before.
        auto['proxies'] = [control if x == name else x for x in auto['proxies']]
    groups.append({'name': GATE, 'type': 'fallback', 'proxies': ['JP-TUIC', 'JP-HY2'],
                   'url': 'https://www.gstatic.com/generate_204', 'expected-status': '204',
                   'interval': 30, 'timeout': 8000, 'lazy': True, 'max-failed-times': 2})
    return profile
