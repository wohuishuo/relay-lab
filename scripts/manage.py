#!/usr/bin/env python3
"""Run from Windows with python; from Ubuntu with python3. Never echo secrets."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jp.common import ROOT, image, private_directory, read_json, run, write_private, state_lock
from jp.config import PROTOCOLS, validate_state


def main():
    parser = argparse.ArgumentParser(description='Personal Japanese proxy project lifecycle')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    sub.add_parser('pull')
    p = sub.add_parser('install-tools')
    p.add_argument('--directory', required=True)
    p = sub.add_parser('local-test')
    p.add_argument('--state', required=True)
    p.add_argument('--protocols', nargs='+', choices=PROTOCOLS)
    p.add_argument('--keep', action='store_true')
    p = sub.add_parser('prepare')
    p.add_argument('--state', required=True)
    p.add_argument('--settings', required=True)
    p.add_argument('--reuse-secrets-from')
    for name in ('validate', 'deploy'):
        p = sub.add_parser(name)
        p.add_argument('--state', required=True)
        p.add_argument('--release', required=True)
    for name in ('rollback', 'status', 'stop'):
        p = sub.add_parser(name)
        p.add_argument('--state', required=True)
    p = sub.add_parser('export-client')
    p.add_argument('--state', required=True)
    p.add_argument('--release', required=True)
    p.add_argument('--protocol', required=True, choices=PROTOCOLS)
    p.add_argument('--output', required=True)
    p = sub.add_parser('backup')
    p.add_argument('--state', required=True)
    p.add_argument('--recipient-file', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--age', default='age')
    p = sub.add_parser('restore')
    p.add_argument('--input', required=True)
    p.add_argument('--identity', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--age', default='age')
    p = sub.add_parser('install-cert')
    p.add_argument('--state', required=True)
    p.add_argument('--certificate', required=True)
    p.add_argument('--key', required=True)
    p.add_argument('--domain', required=True)
    p = sub.add_parser('acme')
    p.add_argument('--state', required=True)
    p.add_argument('--domain', required=True)
    p.add_argument('--email', required=True)
    p.add_argument('--provider', required=True)
    p.add_argument('--credentials', required=True)
    p.add_argument('--lego', default='lego')
    p.add_argument('--staging', action='store_true')
    args = parser.parse_args()
    if hasattr(args, 'state'):
        args.state = validate_state(args.state, ROOT)
    if hasattr(args, 'state') and args.command not in ('status',):
        with state_lock(args.state):
            execute(args)
    else:
        execute(args)


def execute(args):
    cmd = args.command
    if cmd == 'doctor':
        for command in (['docker', 'version', '--format', '{{json .}}'], ['docker', 'compose', 'version']):
            result = run(command, check=False, timeout=30)
            print(result.stdout.strip())
            if result.returncode:
                raise RuntimeError('Docker engine unavailable')
        print('Python:', sys.version.split()[0])
    elif cmd == 'pull':
        for name in ('mihomo', 'mihomo_previous', 'python'):
            print('Pulling locked image:', name, flush=True)
            run(['docker', 'pull', '--platform', 'linux/amd64', image(name)], timeout=300)
        print(run(['docker', 'run', '--rm', '--network', 'none', image(), '-v']).stdout.strip())
    elif cmd == 'install-tools':
        from jp.tools import install_tools
        install_tools(validate_state(args.directory, ROOT))
        print('Verified utilities installed')
    elif cmd == 'local-test':
        from jp.local import run_suite
        report = run_suite(args.state, args.protocols, keep=args.keep)
        print('Local suite:', report['status'])
    elif cmd == 'prepare':
        from jp.operations import prepare
        release = prepare(args.state, read_json(args.settings), prior=args.reuse_secrets_from)
        print('Prepared release:', release)
    elif cmd in ('validate', 'deploy'):
        from jp.operations import validate_release, deploy
        (validate_release if cmd == 'validate' else deploy)(args.state, args.release)
        print('Configuration validated' if cmd == 'validate' else 'Container started; REAL CLIENT ACCEPTANCE STILL REQUIRED')
    elif cmd == 'rollback':
        from jp.operations import rollback
        print('Restored release:', rollback(args.state))
        print('Real client acceptance is required again')
    elif cmd in ('status', 'stop'):
        from jp.operations import prod_context
        active = read_json(args.state / 'active.json')
        command, env = prod_context(args.state, active['current'])
        result = run(command + (['ps'] if cmd == 'status' else ['stop']), env=env)
        print(result.stdout.strip())
        if cmd == 'status':
            container = run(command + ['ps', '-q', 'mihomo'], env=env).stdout.strip()
            if container:
                print(run(['docker', 'stats', '--no-stream', '--format', 'Memory={{.MemUsage}} CPU={{.CPUPerc}} Network={{.NetIO}}', container]).stdout.strip())
    elif cmd == 'export-client':
        from jp.operations import release_path
        dest = Path(args.output).resolve()
        if ROOT == dest or ROOT in dest.parents or dest.exists():
            raise ValueError('Client export must be a new file outside the repository')
        source = release_path(args.state, args.release) / 'clients' / (args.protocol + '.yaml')
        if not dest.parent.exists():
            private_directory(dest.parent)
        write_private(dest, source.read_text(encoding='utf-8'))
        if os.name == 'nt':
            import getpass
            run(['icacls', str(dest), '/inheritance:r', '/grant:r', getpass.getuser() + ':F'])
        print('Client exported privately; import file into a compatible Mihomo client')
    elif cmd == 'backup':
        from jp.operations import backup
        print('Encrypted backup SHA256:', backup(args.state, Path(args.recipient_file).read_text().strip(), args.output, args.age))
    elif cmd == 'restore':
        from jp.operations import restore
        restore(args.input, args.identity, args.output, args.age)
        print('Restored into a new private directory; validate before deployment')
    elif cmd == 'install-cert':
        from jp.certificates import install_pair
        if (args.state / 'active.json').exists():
            from jp.renewal import replace_and_reload
            replace_and_reload(args.state, args.certificate, args.key, args.domain)
        else:
            private_directory(args.state)
            install_pair(args.state, args.certificate, args.key, args.domain)
        print('Certificate installed; real-client certificate/connection verification remains required')
    elif cmd == 'acme':
        from jp.certificates import acme
        private_directory(args.state)
        cert, key = acme(args.state, args.domain, args.email, args.provider, args.credentials, args.lego, staging=args.staging)
        if args.staging:
            print('ACME staging succeeded; untrusted staging certificate was NOT installed')
        else:
            from jp.renewal import replace_and_reload
            replace_and_reload(args.state, cert, key, args.domain)
            print('Certificate renewal/load completed; client acceptance remains required')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('STOPPED: interrupted; no success claimed', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        # Do not expose tracebacks with secret-bearing upstream output.
        print('FAILED:', str(exc), file=sys.stderr)
        sys.exit(1)
