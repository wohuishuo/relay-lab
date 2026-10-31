"""Generate a separate mobile profile from explicitly tested independent nodes."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jp.client_policy import BALANCED_DOMAINS, mobile_profile
from jp.common import private_directory, read_json, write_private


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='Private JSON-formatted client profile')
    parser.add_argument('--output', required=True, help='New private path outside the repository')
    parser.add_argument('--candidate', action='append', required=True, help='Externally tested independent node name; repeat as needed')
    parser.add_argument('--balanced', action='store_true', help='Use the documented small domestic direct list')
    parser.add_argument('--direct-domain', action='append', default=[])
    args = parser.parse_args()
    out = Path(args.output).resolve()
    if out.is_relative_to(Path(__file__).resolve().parents[1]) or out.exists() or out == Path(args.input).resolve():
        parser.error('Choose a new private output file outside this repository')
    domains = (list(BALANCED_DOMAINS) if args.balanced else []) + args.direct_domain
    profile = mobile_profile(read_json(args.input), candidates=args.candidate, direct_domains=domains)
    # Do not change permissions on an arbitrary existing parent directory.
    if not out.parent.exists():
        private_directory(out.parent)
    write_private(out, profile)
    print('Private mobile profile generated. Validate with the target core and phone; credentials suppressed.')


if __name__ == '__main__':
    main()
