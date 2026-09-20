#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jp.bundle import bundle
from jp.common import ROOT, private_directory, read_json, write_private
from jp.config import validate_state
from jp.operations import release_path


def main():
    p = argparse.ArgumentParser(description='Create an offline private client profile')
    p.add_argument('--state', required=True)
    p.add_argument('--release', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--mode', choices=['manual', 'fallback', 'url-test'], default='manual')
    p.add_argument('--health-url', default='https://www.gstatic.com/generate_204')
    args = p.parse_args()
    state = validate_state(args.state, ROOT)
    output = validate_state(args.output, ROOT)
    if output.exists():
        raise ValueError('Refusing to overwrite an existing file')
    release = release_path(state, args.release)
    protocols = read_json(release / 'manifest.json')['protocols']
    configs = {name: read_json(release / 'clients' / (name + '.yaml')) for name in protocols}
    result = bundle(configs, args.mode, args.health_url)
    private_directory(output.parent)
    write_private(output, result)
    print('Private profile generated; no server or subscription changed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FAILED:', type(exc).__name__, file=sys.stderr)
        sys.exit(1)
