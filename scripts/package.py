#!/usr/bin/env python3
"""Build an upload ZIP from an allowlist; private state is never included."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_DIRS = {'jp', 'scripts', 'tests', 'templates', 'docs', 'reports', 'lab', '.github'}
ALLOWED_EXT = {'.py', '.sh', '.md', '.json', '.yaml', '.yml', '.service', '.timer', '.svg', '.css', '.js'}
ROOT_FILES = {'README.md', 'LICENSE', 'SECURITY.md', 'THIRD_PARTY.md', '.gitignore', '.gitattributes',
              'install.sh', 'requirements-docs.txt', 'compose.local.yaml', 'compose.prod.yaml',
              'compose.subscription.yaml', 'compose.bench.yaml', 'compose.failover.yaml', 'versions.lock.json'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    import subprocess
    subprocess.run([sys.executable, ROOT / 'scripts/scan-secrets.py'], check=True)
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError('Refusing to overwrite an existing upload ZIP')
    files = []
    for file in ROOT.rglob('*'):
        if not file.is_file() or file.is_symlink():
            continue
        rel = file.relative_to(ROOT)
        if file.name in ROOT_FILES and len(rel.parts) == 1:
            files.append(file)
        elif rel.parts[0] in ALLOWED_DIRS and (file.suffix in ALLOWED_EXT or file.name == 'Dockerfile.netem') and '__pycache__' not in rel.parts and 'raw' not in rel.parts:
            files.append(file)
    for file in files:
        text = file.read_text(encoding='utf-8')
        # Private key armor is never expected in any source/report/template.
        markers = ['-----BEGIN ' + kind + 'PRIVATE KEY-----' for kind in ('', 'RSA ', 'OPENSSH ')]
        if any(marker in text for marker in markers):
            raise ValueError('Private-key marker detected; package aborted')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(files):
            archive.write(file, 'relay-lab/' + file.relative_to(ROOT).as_posix())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(digest + '  ' + output.name + '\n', encoding='ascii')
    print(json.dumps({'files': len(files), 'bytes': output.stat().st_size, 'sha256': digest}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FAILED:', str(exc), file=sys.stderr)
        sys.exit(1)
