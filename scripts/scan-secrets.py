#!/usr/bin/env python3
"""Conservative prepublication check; reports locations, never matched values."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    'private-key': re.compile(rb'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----'),
    'age-identity': re.compile(rb'AGE-SECRET-KEY-1[A-Z0-9]{40,}'),
    'github-token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
    'cloudflare-token': re.compile(rb'cfut_[A-Za-z0-9_-]{25,}'),
    'personal-windows-path': re.compile(rb'[A-Za-z]:[\\/]Users[\\/](?!Public|USER|<|example)[^\s"\n]+'),
}
SKIP = {'.git', '__pycache__', '.venv', 'site', 'dist'}


def findings(path, data, denied=()):
    result = [name for name, pattern in PATTERNS.items() if pattern.search(data)]
    if any(value.encode() in data for value in denied if value):
        result.append('private-denylist')
    return [{'file': path, 'rule': name} for name in result]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--deny-file', help='Private JSON array of values; must be outside repository')
    args = p.parse_args()
    denied = []
    if args.deny_file:
        path = Path(args.deny_file).resolve()
        if ROOT in path.parents:
            raise ValueError('Private denylist must be outside repository')
        denied = json.loads(path.read_text(encoding='utf-8'))
    result = []
    for path in ROOT.rglob('*'):
        rel = path.relative_to(ROOT)
        if any(part in SKIP for part in rel.parts):
            continue
        if path.is_symlink():
            result.append({'file': rel.as_posix(), 'rule': 'symlink-not-publishable'})
        elif path.is_file():
            result += findings(rel.as_posix(), path.read_bytes(), denied)
    print(json.dumps({'status': 'failed' if result else 'passed', 'findings': result}, indent=2))
    return bool(result)


if __name__ == '__main__':
    sys.exit(main())
