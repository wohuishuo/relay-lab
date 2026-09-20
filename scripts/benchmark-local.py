#!/usr/bin/env python3
"""Isolated, bounded local experiment. No production URL, SSH, or host networking."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jp.common import ROOT, image, private_directory, read_json, run, write_private
from jp.config import PROTOCOLS, client_config, server_config, validate_state
from jp.certificates import generate_test_certs
from jp.local import generate_secrets, lab_env, readable_write
from jp.measurements import aggregate

SCENARIOS = {
    'baseline': ([], []),
    'rtt80': (['delay', '40ms'], ['delay', '40ms']),
    'download-loss': (['delay', '40ms'], ['delay', '40ms', 'loss', '1%']),
    'upload-loss': (['delay', '40ms', 'loss', '1%'], ['delay', '40ms']),
    'download-cap': (['delay', '40ms'], ['delay', '40ms', 'rate', '2mbit']),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', required=True)
    parser.add_argument('--protocols', nargs='+', choices=PROTOCOLS, default=list(PROTOCOLS))
    parser.add_argument('--scenarios', nargs='+', choices=SCENARIOS, default=['baseline'])
    parser.add_argument('--mib', type=int, choices=range(1, 17), default=2)
    parser.add_argument('--repeats', type=int, choices=range(1, 6), default=3)
    args = parser.parse_args()
    state = private_directory(validate_state(args.state, ROOT))
    if (state / 'lab-secrets.json').exists():
        raise ValueError('Use a fresh external state directory')
    env = lab_env(state)
    env['JP_LAB_PROJECT'] = 'relay-bench-' + hashlib.sha256(str(state).encode()).hexdigest()[:10]
    command = ['docker', 'compose', '-p', env['JP_LAB_PROJECT'], '-f', str(ROOT / 'compose.local.yaml'), '-f', str(ROOT / 'compose.bench.yaml')]
    def compose(*cmd, check=True, timeout=120):
        return run(command + list(cmd), env=env, check=check, timeout=timeout)
    secret = generate_secrets()
    write_private(state / 'lab-secrets.json', secret)
    generate_test_certs(state / 'certs')
    os.chmod(state / 'certs', 0o755)
    readable_write(state / 'client/ca.crt', (state / 'certs/ca.crt').read_text())
    readable_write(state / 'server/server.yaml', server_config(args.protocols, secret, 'node.test', 'reality.test:18444', 'reality.test', local=True))
    readable_write(state / 'client/client.yaml', client_config(args.protocols[0], secret, 'server', 'node.test', 'reality.test', local=True))
    report = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'local Docker only; no WAN or production traffic', 'server_image': image(),
              'payload_mib_per_transfer': args.mib, 'repeats': args.repeats,
              'application': 'HTTP/1.1, one connection, no content compression, SHA256 payload verification',
              'measurement': 'goodput includes request setup; first_chunk_ms is first 64KiB, not pure TLS handshake or TTFB',
              'status': 'running', 'results': []}
    def cid(service):
        return compose('ps', '-q', service).stdout.strip()
    def shape(service, tokens):
        container = cid(service)
        info = json.loads(run(['docker', 'inspect', container]).stdout)[0]
        if info['Config']['Labels'].get('com.docker.compose.project') != env['JP_LAB_PROJECT']:
            raise RuntimeError('Refuse to alter a non-lab network namespace')
        front = next(n for n in info['NetworkSettings']['Networks'] if n.endswith('_front'))
        address = info['NetworkSettings']['Networks'][front]['IPAddress']
        base = ['docker', 'run', '--rm', '--network', 'container:' + container, '--cap-drop', 'ALL',
                '--cap-add', 'NET_ADMIN', '--security-opt', 'no-new-privileges:true',
                '--read-only', '--log-driver', 'none', 'relay-lab-netem:local']
        interfaces = json.loads(run(base + ['ip', '-j', 'address', 'show']).stdout)
        interface = next(i['ifname'] for i in interfaces if any(a.get('local') == address for a in i.get('addr_info', [])))
        if tokens:
            run(base + ['tc', 'qdisc', 'replace', 'dev', interface, 'root', 'netem', 'limit', '10000'] + tokens)
        else:
            run(base + ['tc', 'qdisc', 'del', 'dev', interface, 'root'], check=False)
        return run(base + ['tc', '-s', 'qdisc', 'show', 'dev', interface]).stdout.strip()
    try:
        compose('up', '-d', 'target', 'server', 'client')
        target_info = json.loads(run(['docker', 'inspect', cid('target')]).stdout)[0]
        target_ip = next(iter(target_info['NetworkSettings']['Networks'].values()))['IPAddress']
        # A direct connection must fail; the target has no front-network attachment.
        isolated = compose('run', '--rm', '--no-deps', '-T', '--entrypoint', 'python', 'probe',
            '/tests/probe.py', 'isolation', '--target', target_ip)
        report['direct_target_isolation'] = json.loads(isolated.stdout)['passed']
        for scenario in args.scenarios:
            for protocol in args.protocols:
                readable_write(state / 'client/client.yaml', client_config(protocol, secret, 'server', 'node.test', 'reality.test', local=True, target_ip=target_ip))
                compose('up', '-d', '--force-recreate', 'client')
                entry = {'scenario': scenario, 'protocol': protocol}
                if scenario != 'baseline' or any(s != 'baseline' for s in args.scenarios):
                    entry['qdisc_client'] = shape('client', SCENARIOS[scenario][0])
                    entry['qdisc_server'] = shape('server', SCENARIOS[scenario][1])
                result = compose('run', '--rm', '--no-deps', '-T', 'probe', '--mib', str(args.mib), '--repeats', str(args.repeats), timeout=600)
                entry['samples'] = json.loads(result.stdout)
                entry['summary'] = {d: aggregate([r for r in entry['samples']['transfers'] if r['direction'] == d]) for d in ('download', 'upload')}
                entry['passed'] = all(s['all_passed'] for s in entry['summary'].values()) and all(r['ok'] for r in entry['samples']['latency'])
                report['results'].append(entry)
                write_private(state / 'benchmark.json', report)
                print(json.dumps({'scenario': scenario, 'protocol': protocol, 'passed': entry['passed'], 'summary': entry['summary']}), flush=True)
        report['status'] = 'passed' if all(r['passed'] for r in report['results']) else 'partial'
    except Exception as exc:
        report['status'] = 'failed'
        report['error'] = str(exc)
        raise
    finally:
        report['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_private(state / 'benchmark.json', report)
        compose('down', '--remove-orphans', check=False)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('FAILED:', str(exc), file=sys.stderr)
        sys.exit(1)
