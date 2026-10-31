"""Generate a separate profile. Does not publish it or change an active client."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jp.client_policy import BALANCED_DOMAINS, stable_profile
from jp.common import read_json, write_private


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='Existing JSON-formatted client profile')
    parser.add_argument('--output', required=True, help='Private output path outside the repository')
    parser.add_argument('--balanced', action='store_true', help='Direct the documented small domestic domain list')
    parser.add_argument('--direct-domain', action='append', default=[])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(args.output).resolve()
    if out.is_relative_to(root) or out == Path(args.input).resolve() or out.exists():
        parser.error('Choose a new private output file outside this repository')
    domains = (list(BALANCED_DOMAINS) if args.balanced else []) + args.direct_domain
    write_private(out, stable_profile(read_json(args.input), direct_domains=domains))
    print('Private profile generated; credentials suppressed. Validate with the actual client core before use.')


if __name__ == '__main__':
    main()
