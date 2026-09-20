import copy
import datetime
import json
import os
import secrets
import time
import uuid
import hashlib
import ssl
from pathlib import Path
from .common import ROOT, docker_available, image, private_directory, read_json, run, write_private
from .config import PORTS, PROTOCOLS, server_config, client_config, validate_state
from .certificates import generate_test_certs, issue_test_leaf


def generate_secrets(core_image=None):
    text = run(['docker', 'run', '--rm', '--network', 'none', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges:true', core_image or image(),
                'generate', 'reality-keypair']).stdout
    keys = {}
    for line in text.splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            keys[k.strip().lower().replace(' ', '')] = v.strip()
    private = keys.get('privatekey') or keys.get('private-key')
    public = keys.get('publickey') or keys.get('public-key')
    if not private or not public:
        raise RuntimeError('Unexpected upstream REALITY key generator output; no secrets printed')
    return {'uuid': str(uuid.uuid4()), 'reality_private': private, 'reality_public': public,
            'short_id': secrets.token_hex(8), 'passwords': {p: secrets.token_urlsafe(32) for p in PROTOCOLS}}


def lab_env(directory, core_image=None):
    return dict(os.environ, JP_LAB_DIR=str(Path(directory).resolve()),
                JP_LAB_PROJECT='relay-lab-' + hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest()[:10],
                JP_MIHOMO_IMAGE=core_image or image(), JP_PYTHON_IMAGE=image('python'))


def compose(env, *args, check=True, timeout=120):
    result = run(['docker', 'compose', '-p', env['JP_LAB_PROJECT'], '-f', ROOT / 'compose.local.yaml', *args],
                 env=env, timeout=timeout, check=False, cwd=ROOT)
    if check and result.returncode:
        raise RuntimeError(f'Local Compose {args[0]} failed (exit {result.returncode}); private output suppressed')
    return result


def readable_write(path, obj):
    write_private(path, obj)
    os.chmod(Path(path).parent, 0o755)
    os.chmod(path, 0o644)


def probe(env, kind, *, negative=False, target=None, wait_seconds=20):
    args = ['run', '--rm', '--no-deps', '-T', 'probe', kind, '--wait-seconds', str(wait_seconds)]
    if negative:
        args.append('--deny')
    if target:
        args += ['--target', target]
    r = compose(env, *args, check=False, timeout=wait_seconds + 25)
    if r.returncode:
        raise RuntimeError(f'{kind} probe failed ({"negative" if negative else "positive"}); target forwarding not verified')
    return {'check': kind, 'negative': negative, 'passed': True}


def verify_versions(directory, protocols):
    """Check every enabled ingress after each real server image replacement."""
    directory = Path(directory)
    env = lab_env(directory)
    secret = read_json(directory / 'lab-secrets.json')
    target_id = compose(env, 'ps', '-q', 'target').stdout.strip()
    addresses = json.loads(run(['docker', 'inspect', target_id]).stdout)[0]['NetworkSettings']['Networks']
    target_ip = next(iter(addresses.values()))['IPAddress']
    results = {}
    for label, core in [('downgrade-1.19.30', image('mihomo_previous')), ('upgrade-1.19.31', image())]:
        print(f'Testing {label}: all {len(protocols)} enabled protocols', flush=True)
        compose(lab_env(directory, core), 'up', '-d', '--force-recreate', 'server', timeout=240)
        results[label] = {}
        for p in protocols:
            readable_write(directory / 'client/client.yaml', client_config(p, secret, 'server', 'node.test', 'reality.test', local=True, target_ip=target_ip))
            compose(env, 'up', '-d', '--force-recreate', 'client')
            probe(env, 'tcp')
            probe(env, 'udp')
            results[label][p] = 'passed'
    return results


def run_suite(directory, protocols=None, *, keep=False):
    directory = private_directory(validate_state(directory, ROOT))
    docker_available()
    if (directory / 'lab-secrets.json').exists():
        raise ValueError('Use a fresh lab directory for an independent test run')
    env = lab_env(directory)
    secret = generate_secrets()
    write_private(directory / 'lab-secrets.json', secret)
    generate_test_certs(directory / 'certs')
    os.chmod(directory / 'certs', 0o755)
    ca = (directory / 'certs/ca.crt').read_text()
    readable_write(directory / 'client/ca.crt', ca)
    report = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'local Docker only; no VPS or device-app validation',
              'server_image': image(), 'client_image': image(), 'protocols': {},
              'lifecycle': {}, 'production': 'pending', 'status': 'running'}
    protocols = list(protocols or PROTOCOLS)
    try:
        compose(env, 'down', '--remove-orphans')
        for p in protocols:
            report['protocols'][p] = {'status': 'running', 'checks': []}
            checks = report['protocols'][p]['checks']
            print(f'Testing {p}: parse, authenticated TCP/UDP, credential rejection, TLS checks', flush=True)
            cfg = server_config([p], secret, 'node.test', 'reality.test:18444', 'reality.test', local=True)
            client = client_config(p, secret, 'server', 'node.test', 'reality.test', local=True)
            readable_write(directory / 'server/server.yaml', cfg)
            readable_write(directory / 'client/client.yaml', client)
            compose(env, 'run', '--rm', '--no-deps', '-T', 'server', '-t', '-d', '/tmp/check', '-f', '/config/server.yaml')
            compose(env, 'run', '--rm', '--no-deps', '-T', 'client', '-t', '-d', '/tmp/check', '-f', '/config/client.yaml')
            checks.append({'check': 'server-and-client-parse', 'passed': True})
            compose(env, 'up', '-d', '--force-recreate', 'target', 'server', 'client')
            time.sleep(1)
            target_id = compose(env, 'ps', '-q', 'target').stdout.strip()
            addresses = json.loads(run(['docker', 'inspect', target_id]).stdout)[0]['NetworkSettings']['Networks']
            target_ip = next(iter(addresses.values()))['IPAddress']
            # UDP outbound address resolution happens on the client. Back-network DNS
            # is deliberately unavailable there; use the observed IP, not another network attachment.
            client['hosts'] = {'target': target_ip}
            readable_write(directory / 'client/client.yaml', client)
            compose(env, 'up', '-d', '--force-recreate', 'client')
            checks.append(probe(env, 'isolation', target=target_ip))
            for kind in ('tcp', 'udp'):
                checks.append(probe(env, kind))
            bad = copy.deepcopy(client)
            node = bad['proxies'][0]
            node['uuid' if p in ('reality', 'xhttp', 'ws', 'grpc') else 'password'] = (
                str(uuid.uuid4()) if p in ('reality', 'xhttp', 'ws', 'grpc') else secrets.token_urlsafe(32))
            readable_write(directory / 'client/client.yaml', bad)
            compose(env, 'up', '-d', '--force-recreate', 'client')
            for kind in ('tcp', 'udp'):
                checks.append(probe(env, kind, negative=True))
            if p == 'ss':
                bad_cipher = copy.deepcopy(client)
                bad_cipher['proxies'][0]['cipher'] = 'aes-128-gcm'
                readable_write(directory / 'client/client.yaml', bad_cipher)
                compose(env, 'up', '-d', '--force-recreate', 'client')
                for kind in ('tcp', 'udp'):
                    result = probe(env, kind, negative=True)
                    result['check'] = 'wrong-cipher-' + kind
                    checks.append(result)
            if p not in ('ss', 'reality'):
                for variant in ('untrusted-ca', 'wrong-hostname'):
                    bad = copy.deepcopy(client)
                    readable_write(directory / 'client/ca.crt', ca)
                    if variant == 'untrusted-ca':
                        readable_write(directory / 'client/ca.crt', (directory / 'certs/wrong-ca.crt').read_text())
                    else:
                        bad['proxies'][0]['servername' if p in ('xhttp', 'ws', 'grpc') else 'sni'] = 'wrong.test'
                    readable_write(directory / 'client/client.yaml', bad)
                    compose(env, 'up', '-d', '--force-recreate', 'client')
                    result = probe(env, 'tcp', negative=True)
                    result['check'] = variant
                    checks.append(result)
                readable_write(directory / 'client/ca.crt', ca)
            elif p == 'reality':
                bad = copy.deepcopy(client)
                bad['proxies'][0]['reality-opts']['public-key'] = generate_secrets()['reality_public']
                readable_write(directory / 'client/client.yaml', bad)
                compose(env, 'up', '-d', '--force-recreate', 'client')
                result = probe(env, 'tcp', negative=True)
                result['check'] = 'wrong-reality-public-key'
                checks.append(result)
            readable_write(directory / 'client/client.yaml', client)
            compose(env, 'up', '-d', '--force-recreate', 'client')
            checks.append(probe(env, 'tcp'))
            compose(env, 'restart', 'server')
            started = time.monotonic()
            recovered = probe(env, 'tcp', wait_seconds=60)
            recovered['check'] = 'restart-tcp-recovery'
            recovered['elapsed_seconds'] = round(time.monotonic() - started, 2)
            checks.append(recovered)
            checks.append(probe(env, 'udp'))
            report['protocols'][p]['status'] = 'passed'
            write_private(directory / 'report.json', report)
            print(f'{p}: passed', flush=True)
        # All enabled listeners coexist; keep this configuration for lifecycle probes.
        readable_write(directory / 'server/server.yaml', server_config(protocols, secret, 'node.test', 'reality.test:18444', 'reality.test', local=True))
        compose(env, 'up', '-d', '--force-recreate', 'server')
        for p in protocols:
            readable_write(directory / 'client/client.yaml', client_config(p, secret, 'server', 'node.test', 'reality.test', local=True, target_ip=target_ip))
            compose(env, 'up', '-d', '--force-recreate', 'client')
            probe(env, 'tcp')
            probe(env, 'udp')
        report['lifecycle']['all-listeners-coexist'] = 'passed'
        report['version_matrix'] = verify_versions(directory, protocols)
        for label in report['version_matrix']:
            report['lifecycle'][label] = 'passed'
        old_der = ssl.PEM_cert_to_DER_cert((directory / 'certs/server.crt').read_text())
        issue_test_leaf(directory / 'certs')
        new_der = ssl.PEM_cert_to_DER_cert((directory / 'certs/server.crt').read_text())
        if old_der == new_der:
            raise RuntimeError('Certificate rotation did not create a new certificate')
        compose(env, 'restart', 'server', 'target')
        probe(env, 'tcp', wait_seconds=60)
        tls_protocol = next((p for p in protocols if p in ('anytls','trojan','xhttp','ws','grpc')), None)
        if tls_protocol:
            fingerprint = hashlib.sha256(new_der).hexdigest()
            compose(env, 'run', '--rm', '--no-deps', '-T', 'probe', 'certificate', '--tls-port', str(PORTS[tls_protocol][1]), '--fingerprint', fingerprint)
            report['lifecycle']['new-certificate-observed'] = fingerprint
        report['lifecycle']['certificate-replacement-and-restart'] = 'passed'
        report['status'] = 'passed'
        return report
    except Exception as exc:
        report['status'] = 'failed'
        report['error'] = str(exc)
        for entry in report['protocols'].values():
            if entry['status'] == 'running':
                entry['status'] = 'failed'
        raise
    finally:
        report['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_private(directory / 'report.json', report)
        if not keep:
            compose(env, 'down', '--remove-orphans', check=False)
