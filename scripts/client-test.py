#!/usr/bin/env python3
"""Run on a real client machine AFTER server deployment. Never called by local-test."""
import argparse
import copy
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import struct
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jp.common import image, read_json, run, write_private


def dns_probe(port):
    identity = secrets.token_bytes(2)
    question = b'\x07example\x03com\x00\x00\x01\x00\x01'
    payload = identity + b'\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00' + question
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(6)
        try:
            sock.sendto(payload, ('127.0.0.1', port))
            response = sock.recvfrom(4096)[0]
            return (len(response) >= 12 and response[:2] == identity and response[2] & 0x80 != 0
                    and response[3] & 15 == 0 and int.from_bytes(response[6:8], 'big') > 0)
        except OSError:
            return False


def check_config(cfg):
    if len(cfg.get('proxies', [])) != 1 or cfg.get('rules') != ['MATCH,node']:
        raise ValueError('Use an unmodified single-protocol export')
    if cfg['proxies'][0].get('skip-cert-verify'):
        raise ValueError('TLS verification cannot be disabled')


def main():
    parser = argparse.ArgumentParser(description='Positive and negative real-server protocol acceptance')
    parser.add_argument('--config', required=True)
    parser.add_argument('--expected-exit-ip', required=True)
    parser.add_argument('--ip-url', default='https://api.ipify.org')
    parser.add_argument('--dns-target', default='1.1.1.1:53')
    args = parser.parse_args()
    expected = str(ipaddress.ip_address(args.expected_exit_ip))
    if not args.ip_url.startswith('https://'):
        raise ValueError('IP check endpoint must use HTTPS')
    cfg = read_json(args.config)
    check_config(cfg)
    curl = shutil.which('curl.exe' if os.name == 'nt' else 'curl')
    if not curl:
        raise RuntimeError('curl is required')
    cfg.update({'bind-address': '0.0.0.0', 'allow-lan': True, 'mixed-port': 17890, 'log-level': 'silent'})
    cfg['listeners'] = [{'name': 'udp-check', 'type': 'tunnel', 'listen': '0.0.0.0', 'port': 19000,
                         'network': ['udp'], 'target': args.dns_target}]
    name = 'jp-proxy-client-check-' + secrets.token_hex(4)
    results = []
    with tempfile.TemporaryDirectory(prefix='jp-proxy-client-') as temp:
        root = Path(temp) / 'runtime'
        root.mkdir(mode=0o755)
        def execute(config, negative):
            write_private(root / 'client.yaml', config)
            os.chmod(root / 'client.yaml', 0o644)
            run(['docker', 'run', '-d', '--name', name, '--user', '10001:10001', '--read-only',
                 '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--log-driver', 'none',
                 '--tmpfs', '/tmp:rw,noexec,nosuid,size=32m,mode=1777',
                 '-p', '127.0.0.1::17890/tcp', '-p', '127.0.0.1::19000/udp',
                 '--mount', f'type=bind,src={root},dst=/config,readonly', image(),
                 '-d', '/tmp/mihomo', '-f', '/config/client.yaml'])
            try:
                info = json.loads(run(['docker', 'inspect', name]).stdout)[0]
                ports = info['NetworkSettings']['Ports']
                tcp_port = int(ports['17890/tcp'][0]['HostPort'])
                udp_port = int(ports['19000/udp'][0]['HostPort'])
                for _ in range(30):
                    try:
                        with socket.create_connection(('127.0.0.1', tcp_port), timeout=1):
                            break
                    except OSError:
                        time.sleep(.25)
                else:
                    raise RuntimeError('Test client failed to start')
                r = run([curl, '--silent', '--show-error', '--fail', '--max-time', '20',
                         '--noproxy', '', '--proxy', f'http://127.0.0.1:{tcp_port}', args.ip_url], check=False, timeout=25)
                tcp_ok = r.returncode == 0 and r.stdout.strip() == expected
                udp_ok = dns_probe(udp_port)
                # Wrong credentials must yield no successful HTTP response, not merely a different IP.
                passed = (r.returncode != 0 and not udp_ok) if negative else tcp_ok and udp_ok
                result = {'negative_credentials': negative, 'passed': passed,
                          'curl_exit_code': r.returncode,
                          'tcp': 'denied' if r.returncode else ('expected-exit' if tcp_ok else 'unexpected-exit'),
                          'udp': 'received' if udp_ok else 'no-response'}
                results.append(result)
                if not passed:
                    print(json.dumps({'protocol': cfg['proxies'][0]['type'],
                                      'tests': results, 'passed': False}), flush=True)
                    raise RuntimeError('Protocol acceptance failed; endpoint/UDP availability also affects this test')
            finally:
                run(['docker', 'rm', '-f', name], check=False)
        execute(cfg, False)
        bad = copy.deepcopy(cfg)
        node = bad['proxies'][0]
        if node['type'] == 'vless':
            node['uuid'] = str(uuid.uuid4())
        else:
            node['password'] = secrets.token_urlsafe(32)
        execute(bad, True)
        execute(cfg, False)
    print(json.dumps({'protocol': cfg['proxies'][0]['type'], 'tests': results, 'passed': True}, indent=2))
    print('Also test the actual phone/desktop app; record its app and embedded core versions.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FAILED:', str(exc), file=sys.stderr)
        sys.exit(1)
