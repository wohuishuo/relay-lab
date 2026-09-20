#!/usr/bin/env python3
"""Optional private HTTPS subscription. Never prints the credential-bearing URL."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jp.common import state_lock
from jp.subscription import prepare, deploy, check, refresh_certificate, publish, rotate, stop


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['prepare', 'deploy', 'check', 'refresh-cert', 'publish', 'rotate', 'stop'])
    p.add_argument('--state', required=True, type=Path)
    p.add_argument('--client', type=Path)
    p.add_argument('--domain')
    p.add_argument('--port', type=int, default=2087)
    p.add_argument('--bind', default='127.0.0.1')
    p.add_argument('--public', action='store_true')
    args = p.parse_args()
    with state_lock(args.state):
        if args.command == 'prepare':
            if not args.client or not args.domain:
                raise ValueError('prepare requires --client and --domain')
            prepare(args.state, args.client, args.domain, port=args.port, bind=args.bind)
        elif args.command == 'deploy':
            deploy(args.state)
        elif args.command == 'check':
            check(args.state, public=args.public)
        elif args.command == 'refresh-cert':
            refresh_certificate(args.state)
        elif args.command == 'rotate':
            rotate(args.state)
        elif args.command == 'publish':
            if not args.client:
                raise ValueError('publish requires --client')
            publish(args.state, args.client)
        else:
            stop(args.state)
    print('Subscription operation completed; credential-bearing URL remains in private url.txt')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FAILED:', str(exc), file=sys.stderr)
        sys.exit(1)
