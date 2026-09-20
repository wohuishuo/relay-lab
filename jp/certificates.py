import os
import shutil
import tempfile
from pathlib import Path
from .common import openssl, run, write_private
from .config import validate_domain


def generate_test_certs(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    cli = openssl()
    for label in ('ca', 'wrong-ca'):
        run([cli, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '7',
             '-keyout', directory / (label + '.key'), '-out', directory / (label + '.crt'),
             '-subj', '/CN=JP-Proxy-Lab-' + label,
             '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign'])
    issue_test_leaf(directory)


def issue_test_leaf(directory):
    directory = Path(directory)
    cli = openssl()
    ext = directory / 'extensions.cnf'
    write_private(ext, 'subjectAltName=DNS:node.test,DNS:reality.test\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
    run([cli, 'req', '-new', '-newkey', 'rsa:2048', '-nodes', '-keyout', directory / 'server.key',
         '-out', directory / 'server.csr', '-subj', '/CN=node.test'])
    run([cli, 'x509', '-req', '-in', directory / 'server.csr', '-CA', directory / 'ca.crt',
         '-CAkey', directory / 'ca.key', '-CAcreateserial', '-days', '5',
         '-extfile', ext, '-out', directory / 'server.crt'])
    # Parent state is private. Container UID must read the leaf; CA keys are never mounted in production.
    for name in ('server.crt', 'server.key', 'ca.crt', 'wrong-ca.crt'):
        os.chmod(directory / name, 0o644)


def check_pair(cert, key, domain, *, ca=None, minimum_seconds=86400):
    validate_domain(domain)
    cli = openssl()
    run([cli, 'x509', '-in', cert, '-noout', '-checkend', str(minimum_seconds)])
    run([cli, 'x509', '-in', cert, '-noout', '-checkhost', domain])
    # OpenSSL checkhost may print mismatch with exit 0 in some versions. Verify explicitly.
    output = run([cli, 'x509', '-in', cert, '-noout', '-checkhost', domain]).stdout
    if 'does NOT match' in output or 'does match' not in output:
        raise ValueError('Certificate hostname mismatch')
    a = run([cli, 'x509', '-in', cert, '-pubkey', '-noout']).stdout
    b = run([cli, 'pkey', '-in', key, '-pubout']).stdout
    if a.strip() != b.strip():
        raise ValueError('Certificate and private key do not match')
    verify = [cli, 'verify', '-untrusted', cert, '-verify_hostname', domain]
    if ca:
        verify += ['-CAfile', ca]
    run(verify + [cert])


def install_pair(state, cert, key, domain, *, ca=None):
    state = Path(state)
    check_pair(cert, key, domain, ca=ca)
    dest = state / 'certs' / 'live'
    dest.mkdir(parents=True, exist_ok=True, mode=0o755)
    for src, name in ((cert, 'server.crt'), (key, 'server.key')):
        write_private(dest / name, Path(src).read_text(encoding='utf-8'))
        if os.name != 'nt':
            os.chown(dest / name, 10001, 10001)
            os.chmod(dest / name, 0o400)


def acme(state, domain, email, provider, credentials_file, lego, *, staging=False):
    """Credentials enter child environment only; no credential values in argv/logs."""
    import json
    import re
    validate_domain(domain)
    if not re.fullmatch(r'[a-z0-9]+', provider):
        raise ValueError('Invalid lego DNS provider ID')
    if '\n' in email or '@' not in email:
        raise ValueError('Invalid account email')
    state = Path(state)
    credentials = json.loads(Path(credentials_file).read_text(encoding='utf-8'))
    if not isinstance(credentials, dict) or not credentials:
        raise ValueError('DNS credentials file must be a nonempty object')
    env = {k: v for k, v in os.environ.items() if not k.startswith('LEGO_')}
    for k, v in credentials.items():
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', k) or not isinstance(v, str):
            raise ValueError('Invalid DNS credential entry')
        # Prevent a credentials file from changing executable lookup or code loading.
        if k.startswith('LEGO_') or k in ('PATH', 'PYTHONPATH', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'HOME'):
            raise ValueError('Not a DNS credential variable')
        env[k] = v
    acme_dir = state / ('acme-staging' if staging else 'acme')
    args = acme_command(lego, acme_dir, domain, email, provider, staging=staging)
    run(args, env=env, timeout=600)
    return acme_dir / 'certificates' / (domain + '.crt'), acme_dir / 'certificates' / (domain + '.key')


def acme_command(lego, acme_dir, domain, email, provider, *, staging=False):
    # lego v5 merged obtain/renew into `run`; v4 `renew --days` is invalid here.
    args = [lego, 'run', '--accept-tos', '--email', email, '--dns', provider,
            '--domains', domain, '--cert.name', domain, '--path', acme_dir, '--renew-days', '30']
    if staging:
        args += ['--server', 'https://acme-staging-v02.api.letsencrypt.org/directory']
    return args
