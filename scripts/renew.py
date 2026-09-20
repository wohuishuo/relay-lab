#!/usr/bin/env python3
"""Installed fresh-host renewal hook. Runtime config remains outside Git."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jp.common import ROOT, read_json, run

if __name__ == '__main__':
    try:
        state = Path('/var/lib/relay-lab')
        cfg = read_json(state / 'renewal.json')
        run([sys.executable, ROOT / 'scripts/manage.py', 'acme', '--state', state,
             '--domain', cfg['domain'], '--email', cfg['email'], '--provider', 'cloudflare',
             '--credentials', cfg['credentials'], '--lego', cfg['lego']], timeout=800)
        if (state / 'subscription' / 'settings.json').exists():
            run([sys.executable, ROOT / 'scripts/subscription.py', 'refresh-cert', '--state', state], timeout=120)
        print('Renewal check/load finished')
    except Exception as exc:
        print('FAILED:', type(exc).__name__, file=sys.stderr)
        sys.exit(1)
