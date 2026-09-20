#!/usr/bin/env python3
"""Standard-library test runner with a small, secret-free machine report."""
import argparse
import datetime
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', default=str(ROOT / 'reports/unit-tests.json'))
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'python': sys.version.split()[0], 'tests': result.testsRun,
              'failures': [t.id() for t, _ in result.failures],
              'errors': [t.id() for t, _ in result.errors],
              'skipped': [{'test': t.id(), 'reason': why} for t, why in result.skipped],
              'status': 'passed' if result.wasSuccessful() and not result.skipped else ('partial' if result.wasSuccessful() else 'failed')}
    dest = Path(args.report)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
