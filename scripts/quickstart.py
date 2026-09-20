#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jp.common import read_json, state_lock
from jp.quickstart import plan, apply


def main():
    p = argparse.ArgumentParser(description='Plan by default; --apply installs on a fresh Ubuntu host')
    p.add_argument('--settings', required=True)
    p.add_argument('--state', default='/var/lib/relay-lab')
    p.add_argument('--email')
    p.add_argument('--credentials')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--firewall-ready', action='store_true')
    p.add_argument('--recovery-ready', action='store_true')
    p.add_argument('--accept-acme-tos', action='store_true')
    args = p.parse_args()
    settings = read_json(args.settings)
    proposal = plan(settings, args.state)
    if not args.apply:
        print(json.dumps(proposal, indent=2))
        return
    if not args.email or not args.credentials:
        raise ValueError('--email and --credentials are required for apply')
    with state_lock(args.state):
        release = apply(settings, args.state, args.email, args.credentials,
                        firewall_ready=args.firewall_ready, recovery_ready=args.recovery_ready,
                        accept_acme_tos=args.accept_acme_tos)
    print('Started release:', release)
    print('PRIVATE client: /var/lib/relay-lab/client.yaml. Real-client acceptance STILL REQUIRED.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FAILED:', str(exc), file=sys.stderr)
        sys.exit(1)
