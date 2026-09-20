"""Version-specific Mihomo configuration generation. JSON is valid YAML."""
import ipaddress
import re
from pathlib import Path

PROTOCOLS = ('reality', 'hy2', 'anytls', 'tuic', 'trojan', 'ss', 'xhttp', 'ws', 'grpc')
PORTS = {'reality': (443, 14443, ('tcp',)), 'hy2': (443, 14443, ('udp',)),
         'anytls': (8443, 18443, ('tcp',)), 'tuic': (8443, 18443, ('udp',)),
         'trojan': (9443, 19443, ('tcp',)), 'ss': (8388, 18388, ('tcp', 'udp')),
         'xhttp': (10443, 20443, ('tcp',)), 'ws': (11443, 21443, ('tcp',)),
         'grpc': (12443, 22443, ('tcp',))}
PRIVATE_V4 = ('0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8',
              '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16', '224.0.0.0/4', '240.0.0.0/4')
PRIVATE_V6 = ('::/128', '::1/128', '::ffff:0:0/96', 'fc00::/7', 'fe80::/10', 'ff00::/8')


def validate_domain(value):
    if not isinstance(value, str) or len(value) > 253 or not re.fullmatch(
        r'(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}', value):
        raise ValueError('A plain DNS hostname is required')
    return value.lower()


def validate_protocols(items):
    if not items or len(set(items)) != len(items) or any(p not in PROTOCOLS for p in items):
        raise ValueError('Choose unique supported protocols')
    return list(items)


def validate_image(value):
    if not re.fullmatch(r'(?:docker.io/)?metacubex/mihomo@sha256:[0-9a-f]{64}', value):
        raise ValueError('Mihomo image must be the upstream repository pinned by SHA256 digest')
    return value


def validate_state(path, repo):
    path, repo = Path(path).resolve(), Path(repo).resolve()
    if path == repo or repo in path.parents or path in repo.parents:
        raise ValueError('Private state must be outside the project and not its ancestor')
    return path


def validate_host(host):
    try:
        ipaddress.ip_address(host)
    except ValueError:
        validate_domain(host)
    return host


def port_bindings(protocols):
    validate_protocols(protocols)
    return [f'0.0.0.0:{PORTS[p][0]}:{PORTS[p][1]}/{transport}' for p in protocols for transport in PORTS[p][2]]


def example_secrets():
    return {'uuid': '00000000-0000-4000-8000-000000000001',
            'reality_private': 'REPLACE_WITH_GENERATED_PRIVATE_KEY',
            'reality_public': 'REPLACE_WITH_GENERATED_PUBLIC_KEY', 'short_id': 'REPLACE_WITH_SHORT_ID',
            'passwords': {p: 'REPLACE_WITH_UNIQUE_GENERATED_PASSWORD' for p in PROTOCOLS}}


def server_config(protocols, secret, domain, reality_dest, reality_sni, *, local=False):
    validate_protocols(protocols)
    validate_domain(domain)
    validate_domain(reality_sni)
    if not re.fullmatch(r'[A-Za-z0-9.-]+:[0-9]{1,5}', reality_dest):
        raise ValueError('REALITY destination must be hostname:port')
    host, port = reality_dest.rsplit(':', 1)
    validate_domain(host)
    if not 1 <= int(port) <= 65535:
        raise ValueError('Invalid REALITY destination port')
    cert = {'certificate': '/certs/server.crt', 'private-key': '/certs/server.key'}
    listeners = []
    for p in protocols:
        item = {'name': p, 'type': p, 'listen': '0.0.0.0', 'port': PORTS[p][1]}
        if p in ('reality', 'xhttp', 'ws', 'grpc'):
            item.update(type='vless', users=[{'username': 'owner', 'uuid': secret['uuid']}])
            if p == 'reality':
                item['users'][0]['flow'] = 'xtls-rprx-vision'
                item['reality-config'] = {'dest': reality_dest, 'server-names': [reality_sni],
                                         'private-key': secret['reality_private'], 'short-id': [secret['short_id']]}
            else:
                item.update(cert)
                if p == 'ws':
                    item['ws-path'] = '/proxy-ws'
                elif p == 'grpc':
                    item['grpc-service-name'] = 'proxygrpc'
                else:
                    item['xhttp-config'] = {'path': '/proxy-xhttp', 'mode': 'packet-up'}
        elif p == 'hy2':
            item.update(cert)
            item.update(type='hysteria2', users={'owner': secret['passwords'][p]}, alpn=['h3'])
            item['ignore-client-bandwidth'] = True
        elif p == 'tuic':
            item.update(cert)
            item.update(users={secret['uuid']: secret['passwords'][p]}, alpn=['h3'])
            item['congestion-controller'] = 'bbr'
        elif p == 'anytls':
            item.update(cert)
            item['users'] = {'owner': secret['passwords'][p]}
        elif p == 'trojan':
            item.update(cert)
            item['users'] = [{'username': 'owner', 'password': secret['passwords'][p]}]
        elif p == 'ss':
            item.update(type='shadowsocks', cipher='chacha20-ietf-poly1305', password=secret['passwords'][p], udp=True)
        listeners.append(item)
    rules = [] if local else ([f'IP-CIDR,{net},REJECT' for net in PRIVATE_V4] +
                              [f'IP-CIDR6,{net},REJECT' for net in PRIVATE_V6])
    return {'mode': 'rule', 'log-level': 'silent', 'ipv6': False, 'allow-lan': False,
            'listeners': listeners, 'rules': rules + ['MATCH,DIRECT'],
            'profile': {'store-selected': False, 'store-fake-ip': False}}


def client_config(protocol, secret, host, domain, reality_sni, *, local=False, target_ip=None):
    validate_protocols([protocol])
    p = protocol
    proxy = {'name': 'node', 'type': p, 'server': host,
             'port': PORTS[p][1 if local else 0], 'udp': True}
    if p in ('reality', 'xhttp', 'ws', 'grpc'):
        proxy.update(type='vless', uuid=secret['uuid'], tls=True, network='tcp', servername=domain)
        proxy['client-fingerprint'] = 'chrome'
        if p == 'reality':
            proxy.update(flow='xtls-rprx-vision', servername=reality_sni)
            proxy['reality-opts'] = {'public-key': secret['reality_public'], 'short-id': secret['short_id']}
        else:
            proxy['network'] = p
            if p == 'ws':
                proxy['ws-opts'] = {'path': '/proxy-ws'}
            elif p == 'grpc':
                proxy['grpc-opts'] = {'grpc-service-name': 'proxygrpc'}
            else:
                proxy['xhttp-opts'] = {'path': '/proxy-xhttp', 'mode': 'packet-up'}
    elif p == 'hy2':
        proxy.update(type='hysteria2', password=secret['passwords'][p], sni=domain, alpn=['h3'])
    elif p == 'tuic':
        proxy.update(uuid=secret['uuid'], password=secret['passwords'][p], sni=domain, alpn=['h3'])
        proxy.update({'congestion-controller': 'bbr', 'udp-relay-mode': 'native'})
    elif p in ('trojan', 'anytls'):
        proxy.update(password=secret['passwords'][p], sni=domain)
    else:
        proxy.update(type='ss', cipher='chacha20-ietf-poly1305', password=secret['passwords'][p])
    if p != 'ss':
        proxy['skip-cert-verify'] = False
    cfg = {'mixed-port': 17890, 'allow-lan': local, 'bind-address': '0.0.0.0' if local else '127.0.0.1',
           'mode': 'rule', 'log-level': 'silent', 'ipv6': False,
           'proxies': [proxy], 'rules': ['MATCH,node']}
    if local:
        if target_ip:
            cfg['hosts'] = {'target': str(ipaddress.ip_address(target_ip))}
        cfg['listeners'] = [{'name': 'udp-probe', 'type': 'tunnel', 'listen': '0.0.0.0',
                             'port': 19000, 'network': ['udp'], 'target': 'target:19000'}]
    return cfg
