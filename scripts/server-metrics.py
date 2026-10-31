#!/usr/bin/env python3
"""Collect once; schedule with a systemd timer. No automatic service restarts."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jp.common import write_private
from jp.metrics import append_bounded, collect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True)
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    state = Path(args.state).resolve()
    if args.show:
        print((state / 'last.json').read_text())
        return
    import fcntl
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sample = collect()
        append_bounded(state, sample)
        write_private(state / 'last.json', sample)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error': type(exc).__name__}), file=sys.stderr)
        sys.exit(1)
