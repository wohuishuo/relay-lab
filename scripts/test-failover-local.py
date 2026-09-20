#!/usr/bin/env python3
"""Test client policy in an isolated lab. No host ports or production access."""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import secrets
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jp.common import ROOT, private_directory, run, write_private
from jp.config import validate_state, server_config, client_config
from jp.local import lab_env, generate_secrets, readable_write
from jp.certificates import generate_test_certs
from jp.bundle import bundle


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--state', required=True)
    args = p.parse_args()
    state = private_directory(validate_state(args.state, ROOT))
    if (state / 'lab-secrets.json').exists():
        raise ValueError('Use a fresh lab state')
    env = lab_env(state)
    env['JP_LAB_PROJECT'] += '-failover'
    def compose(*args, check=True):
        return run(['docker', 'compose', '-p', env['JP_LAB_PROJECT'], '-f', ROOT / 'compose.local.yaml',
                    '-f', ROOT / 'compose.failover.yaml', *args], env=env, check=check)
    secret = generate_secrets()
    write_private(state / 'lab-secrets.json', secret)
    generate_test_certs(state / 'certs')
    os.chmod(state / 'certs', 0o755)
    readable_write(state / 'client/ca.crt', (state / 'certs/ca.crt').read_text())
    api_secret = secrets.token_urlsafe(32)
    readable_write(state / 'client/api-secret.txt', api_secret)
    server = server_config(['ss'], secret, 'node.test', 'reality.test:18444', 'reality.test', local=True)
    second = copy.deepcopy(server['listeners'][0])
    second.update(name='ss-second', port=18389)
    server['listeners'].append(second)
    readable_write(state / 'server/server.yaml', server)
    clients = {n: client_config('ss', secret, 'server', 'node.test', 'reality.test', local=True) for n in ('Primary', 'Backup')}
    clients['Backup']['proxies'][0]['port'] = 18389
    report = {'scope': 'local Docker only; no live profile updated', 'checks': [], 'status': 'running'}
    def record(name):
        report['checks'].append({'check': name, 'passed': True})
        print(name + ': passed', flush=True)
    def select(name):
        compose('run', '--rm', '--no-deps', '-T', '--entrypoint', 'python', 'probe', '/lab/check_selection.py', name)
    def tcp(negative=False):
        compose('run', '--rm', '--no-deps', '-T', 'probe', 'tcp', *(['--deny'] if negative else []))
    try:
        compose('up', '-d', 'target', 'server')
        target = compose('ps', '-q', 'target').stdout.strip()
        networks = json.loads(run(['docker', 'inspect', target]).stdout)[0]['NetworkSettings']['Networks']
        ip = next(iter(networks.values()))['IPAddress']
        for mode in ('manual', 'fallback', 'url-test'):
            cfg = bundle(clients, mode, 'https://reality.test:18444/health')
            cfg.update({'allow-lan': True, 'bind-address': '0.0.0.0', 'hosts': {'reality.test': ip}})
            # Lab-only controller, inside internal network, randomized secret, no host port.
            cfg.update({'external-controller': '0.0.0.0:19091', 'secret': api_secret})
            if mode != 'manual':
                cfg['proxy-groups'][1]['interval'] = 2
            readable_write(state / 'client/client.yaml', cfg)
            compose('run', '--rm', '--no-deps', '-T', 'client', '-t', '-d', '/tmp/check', '-f', '/config/client.yaml')
            compose('up', '-d', '--force-recreate', 'client')
            tcp()
            record(mode + '-authenticated-forwarding')
            if mode == 'manual':
                continue
            if mode == 'fallback':
                select('Primary')
            impaired = copy.deepcopy(server)
            impaired['listeners'] = [second]
            readable_write(state / 'server/server.yaml', impaired)
            compose('up', '-d', '--force-recreate', 'server')
            select('Backup')
            tcp()
            record(mode + '-primary-loss-selects-backup')
            compose('stop', 'server')
            tcp(negative=True)
            record(mode + '-all-down-no-direct-bypass')
            readable_write(state / 'server/server.yaml', server)
            compose('up', '-d', '--force-recreate', 'server')
            if mode == 'fallback':
                select('Primary')
            tcp()
            record(mode + '-recovery')
        report['status'] = 'passed'
    finally:
        report['at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if report['status'] == 'running':
            report['status'] = 'failed'
        write_private(state / 'report.json', report)
        compose('down', '--remove-orphans', check=False)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FAILED:', str(exc), file=sys.stderr)
        sys.exit(1)
