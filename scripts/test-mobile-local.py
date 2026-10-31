"""Bounded live forwarding/fault test in an isolated native client.

Requires an existing private mobile profile and core binary. Does not edit the
active client, server, firewall, or OS routes. Uses small public HTTPS/DNS probes.
"""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import secrets
import select
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jp.common import ROOT, private_directory, read_json, write_private


class Relay:
    def __init__(self, host, port):
        self.remote = (host, port)
        self.local = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.local.bind(('127.0.0.1', 0))
        self.port = self.local.getsockname()[1]
        self.stop = threading.Event()
        self.drop = threading.Event()
        self.counts = {'forwarded': 0, 'dropped': 0}
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        pairs = {}
        try:
            while not self.stop.is_set():
                readable, _, _ = select.select([self.local, *pairs.values()], [], [], .1)
                for sock in readable:
                    try:
                        if sock is self.local:
                            data, addr = sock.recvfrom(65535)
                            if self.drop.is_set():
                                self.counts['dropped'] += 1
                                continue
                            if addr not in pairs:
                                if len(pairs) >= 32:
                                    continue
                                upstream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                                upstream.connect(self.remote)
                                pairs[addr] = upstream
                            pairs[addr].send(data)
                        else:
                            data = sock.recv(65535)
                            if self.drop.is_set():
                                self.counts['dropped'] += 1
                                continue
                            addr = next(a for a, s in pairs.items() if s is sock)
                            self.local.sendto(data, addr)
                        self.counts['forwarded'] += 1
                    except OSError:
                        pass
        finally:
            self.local.close()
            for sock in pairs.values():
                sock.close()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--core', required=True)
    parser.add_argument('--state', required=True, help='New private test directory outside the repository')
    parser.add_argument('--fault', action='store_true', help='Drop relay packets, test failover, all-down and recovery')
    args = parser.parse_args()
    state = Path(args.state).resolve()
    if state.exists() or state.is_relative_to(ROOT):
        parser.error('Use a new private state directory outside the repository')
    private_directory(state)
    source = read_json(args.input)
    # Never inherit TUN, redirect/tproxy listeners, LAN bindings or controller
    # settings from arbitrary input: this test must not touch active OS routes.
    cfg = {key: copy.deepcopy(source[key]) for key in ('proxies', 'proxy-groups', 'dns', 'rules')}
    cfg.update({'allow-lan': False, 'bind-address': '127.0.0.1',
                'mode': 'rule', 'log-level': 'silent', 'ipv6': False})
    nodes = cfg['proxies']
    if len(nodes) != 2 or {n['type'] for n in nodes} != {'tuic', 'hysteria2'}:
        raise ValueError('This fault fixture requires exactly independent TUIC and HY2 nodes')
    if any(n.get('dialer-proxy') or n.get('skip-cert-verify') for n in nodes):
        raise ValueError('Use independent nodes with certificate verification')
    group = next(g for g in cfg['proxy-groups'] if g['name'] == 'JP-MOBILE-AUTO')
    relays = {}
    proc = None
    report = {'scope': 'isolated native client on maintenance computer; not a phone test',
              'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'interval_seconds': group['interval'], 'timeout_ms': group['timeout'],
              'status': 'running'}
    curl = 'curl.exe' if os.name == 'nt' else 'curl'
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    mixed, api, dns_port = free_port(), free_port(), free_port()
    token = secrets.token_urlsafe(32)
    def selected():
        req = urllib.request.Request(f'http://127.0.0.1:{api}/proxies/JP-MOBILE-AUTO',
                                     headers={'Authorization': 'Bearer ' + token})
        with op.open(req, timeout=2) as r:
            return json.load(r)['now']
    def fetch():
        r = subprocess.run([curl, '--silent', '--max-time', '8', '--proxy',
                            f'socks5h://127.0.0.1:{mixed}', '--output', os.devnull,
                            '--write-out', '%{http_code}', 'https://www.gstatic.com/generate_204'],
                           capture_output=True, text=True, timeout=11)
        return r.returncode == 0 and r.stdout == '204'
    def dns(name, kind):
        ident = secrets.randbelow(65536)
        wire = struct.pack('!HHHHHH', ident, 0x100, 1, 0, 0, 0)
        wire += b''.join(bytes([len(x)]) + x.encode() for x in name.split('.'))
        wire += b'\x00' + struct.pack('!HH', kind, 1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(12)
            s.sendto(wire, ('127.0.0.1', dns_port))
            packet, _ = s.recvfrom(8192)
        head = struct.unpack('!HHHHHH', packet[:12])
        assert head[0] == ident and head[1] & 15 == 0 and head[3] > 0
        return {'rcode': head[1] & 15, 'answers': head[3]}
    try:
        for n in nodes:
            # Preserve the original TLS server name when changing only the test socket.
            if not (n.get('sni') or n.get('servername')):
                n['sni'] = n['server']
            relays[n['name']] = Relay(n['server'], n['port'])
            n.update(server='127.0.0.1', port=relays[n['name']].port)
        cfg.update({'mixed-port': mixed, 'external-controller': f'127.0.0.1:{api}', 'secret': token})
        cfg['dns']['listen'] = f'127.0.0.1:{dns_port}'
        write_private(state / 'client.json', cfg)
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        ver = subprocess.run([args.core, '-v'], capture_output=True, text=True, timeout=5)
        report['core_version'] = ver.stdout.splitlines()[0]
        validation = subprocess.run([args.core, '-t', '-d', str(state / 'data'), '-f', str(state / 'client.json')],
                                    capture_output=True, text=True, timeout=30)
        if validation.returncode:
            raise RuntimeError('Core rejected profile; output suppressed')
        report['parse'] = True
        proc = subprocess.Popen([args.core, '-d', str(state / 'data'), '-f', str(state / 'client.json')],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
        for _ in range(60):
            try:
                selected()
                break
            except Exception:
                time.sleep(.2)
        else:
            raise RuntimeError('Isolated client did not start')
        time.sleep(9)
        report['before'] = {'selected': selected(), 'https': fetch()}
        assert report['before']['https']
        report['proxied_txt_dns'] = dns('example.com', 16)
        report['direct_txt_dns'] = dns('qq.com', 16)
        report['direct_a_dns'] = dns('qq.com', 1)
        if args.fault:
            broken = selected()
            relays[broken].drop.set()
            start = time.monotonic()
            samples = []
            while time.monotonic() - start < 90:
                name = selected()
                ok = fetch()
                samples.append({'seconds': round(time.monotonic() - start, 3), 'selected': name, 'https': ok})
                if ok and name != broken:
                    break
                time.sleep(.5)
            report['primary_drop'] = {'node': broken, 'samples': samples}
            assert samples[-1]['https'] and samples[-1]['selected'] != broken
            for relay in relays.values():
                relay.drop.set()
            report['all_down_https'] = [fetch(), fetch()]
            assert not any(report['all_down_https'])
            for relay in relays.values():
                relay.drop.clear()
            start = time.monotonic()
            recovered = False
            while time.monotonic() - start < 90:
                if fetch():
                    recovered = True
                    break
                time.sleep(1)
            report['recovery'] = {'https': recovered, 'seconds': round(time.monotonic() - start, 3)}
            assert recovered
        report['status'] = 'passed'
    except Exception as exc:
        report.update(status='failed', error=type(exc).__name__)
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        for relay in relays.values():
            relay.close()
        report['relay_packet_counts'] = {name: relay.counts for name, relay in relays.items()}
        report['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if report['status'] == 'running':
            report['status'] = 'interrupted'
        write_private(state / 'report.json', report)
        print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
