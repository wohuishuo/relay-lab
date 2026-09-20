import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import uuid
from pathlib import Path, PurePosixPath
from .common import ROOT, image, private_directory, read_json, run, write_private
from .config import PORTS, client_config, port_bindings, server_config, validate_domain, validate_host, validate_image, validate_protocols, validate_state


def activate(state, release, perform):
    path = Path(state) / 'active.json'
    old = read_json(path) if path.exists() else {'current': None, 'previous': None}
    perform()
    write_private(path, {'current': release, 'previous': old['current']})


def extract_safe(stream, target):
    target = Path(target).resolve()
    if target.exists():
        raise ValueError('Restore target must not exist')
    with tarfile.open(fileobj=stream, mode='r:*') as archive:
        members = archive.getmembers()
        total = 0
        names = set()
        for m in members:
            p = PurePosixPath(m.name)
            if p.is_absolute() or '..' in p.parts or '\\' in m.name or ':' in m.name or m.name in names:
                raise ValueError('Unsafe archive path')
            if not (m.isfile() or m.isdir()):
                raise ValueError('Archive links and special files are prohibited')
            names.add(m.name)
            total += m.size
            if total > 256 * 1024 * 1024 or len(names) > 10000:
                raise ValueError('Backup exceeds restore safety limit')
        private_directory(target)
        try:
            archive.extractall(target, members=members, filter='data')
            if os.name != 'nt':
                for p in target.rglob('*'):
                    os.chmod(p, 0o700 if p.is_dir() else 0o600)
        except Exception:
            shutil.rmtree(target)
            raise


def release_path(state, release):
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}', release):
        raise ValueError('Invalid release identifier')
    path = Path(state) / 'releases' / release
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Release directory missing or unsafe')
    return path


def prepare(state, settings, *, prior=None, core_image=None):
    from .local import generate_secrets
    state = private_directory(validate_state(state, ROOT))
    protocols = validate_protocols(settings['protocols'])
    validate_host(settings['server'])
    validate_domain(settings['domain'])
    validate_domain(settings['reality_sni'])
    core_image = validate_image(core_image or image())
    # Validate all public configuration before generating secrets or changing release state.
    from .config import example_secrets
    server_config(protocols, example_secrets(), settings['domain'], settings['reality_dest'], settings['reality_sni'])
    revoked = read_json(state / 'revoked-releases.json') if (state / 'revoked-releases.json').exists() else []
    if prior in revoked:
        raise ValueError('Cannot reuse secrets from a revoked release')
    secret = read_json(release_path(state, prior) / 'secrets.json') if prior else generate_secrets(core_image)
    name = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
    dest = state / 'releases' / name
    dest.mkdir(parents=True, mode=0o700)
    write_private(dest / 'secrets.json', secret)
    write_private(dest / 'settings.json', settings)
    write_private(dest / 'manifest.json', {'release': name, 'image': core_image, 'schema': 1, 'protocols': protocols})
    write_private(dest / 'runtime/server.yaml', server_config(protocols, secret, settings['domain'], settings['reality_dest'], settings['reality_sni']))
    write_private(dest / 'runtime/listeners.expected', ''.join(f'{transport} {PORTS[p][1]:04X}\n' for p in protocols for transport in PORTS[p][2]))
    write_private(dest / 'runtime/healthcheck.sh', (ROOT / 'scripts/healthcheck.sh').read_text(encoding='utf-8'))
    write_private(dest / 'ports.json', {'services': {'mihomo': {'ports': port_bindings(protocols)}}})
    for p in protocols:
        write_private(dest / 'clients' / (p + '.yaml'), client_config(p, secret, settings['server'], settings['domain'], settings['reality_sni']))
    secure_runtime(dest)
    return name


def secure_runtime(release):
    if os.name != 'nt':
        runtime = Path(release) / 'runtime'
        os.chown(runtime, 10001, 10001)
        os.chmod(runtime, 0o500)
        for file in runtime.iterdir():
            if file.is_file():
                os.chown(file, 10001, 10001)
                os.chmod(file, 0o400)


def prod_context(state, release):
    state = Path(state).resolve()
    path = release_path(state, release)
    manifest = read_json(path / 'manifest.json')
    env = dict(os.environ, JP_MIHOMO_IMAGE=validate_image(manifest['image']),
               JP_STATE_DIR=str(state), JP_RELEASE_DIR=str(path))
    args = ['docker', 'compose', '-p', 'jp-proxy', '-f', str(ROOT / 'compose.prod.yaml'), '-f', str(path / 'ports.json')]
    return args, env


def validate_release(state, release):
    from .certificates import check_pair
    path = release_path(state, release)
    settings = read_json(path / 'settings.json')
    check_pair(Path(state) / 'certs/live/server.crt', Path(state) / 'certs/live/server.key', settings['domain'])
    secure_runtime(path)
    args, env = prod_context(state, release)
    run(args + ['config', '--quiet'], env=env)
    run(args + ['run', '--rm', '--no-deps', '-T', 'mihomo', '-t', '-d', '/tmp/check', '-f', '/config/server.yaml'], env=env)


def deploy(state, release, *, rollback=False):
    state = Path(state)
    if os.name == 'nt':
        raise ValueError('Production deploy is Linux-only; run local-test on Windows')
    revoked = read_json(state / 'revoked-releases.json') if (state / 'revoked-releases.json').exists() else []
    if release in revoked:
        raise ValueError('This release has revoked credentials and cannot be deployed')
    validate_release(state, release)
    args, env = prod_context(state, release)
    def perform():
        try:
            run(args + ['up', '-d', '--wait', '--wait-timeout', '75', '--remove-orphans'], env=env, timeout=120)
            # --wait only establishes process/config health, not external protocol acceptance.
            status = run(args + ['ps', '--format', 'json'], env=env).stdout
            if 'unhealthy' in status or 'running' not in status.lower():
                raise RuntimeError('Container did not become healthy')
        except Exception:
            run(args + ['stop'], env=env, check=False)
            write_private(state / 'failed-deployment.json', {'release': release, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
            raise
    activate(state, release, perform)
    write_private(state / 'acceptance-pending.json', {'release': release, 'status': 'awaiting real client TCP/UDP, restart and firewall checks'})


def rollback(state):
    data = read_json(Path(state) / 'active.json')
    if not data.get('previous'):
        raise ValueError('No previous successful release')
    deploy(state, data['previous'], rollback=True)
    return data['previous']


def backup(state, recipient, output, age):
    state, output = Path(state).resolve(), Path(output).resolve()
    if not re.fullmatch(r'age1[0-9a-z]{58}', recipient):
        raise ValueError('Use an age X25519 public recipient')
    if output.exists() or state == output or state in output.parents:
        raise ValueError('Backup must be a new file outside state')
    allowed = ['releases', 'certs', 'active.json', 'revoked-releases.json', 'acme', 'subscription']
    # Small configuration backups are kept in RAM; never write a plaintext tar.
    stream = io.BytesIO()
    total_bytes = 0
    with tarfile.open(fileobj=stream, mode='w:gz', dereference=False) as tar:
        for name in allowed:
            source = state / name
            if not source.exists():
                continue
            paths = [source] + list(source.rglob('*')) if source.is_dir() else [source]
            for p in paths:
                if p.is_symlink():
                    raise ValueError('Backup refuses symlinks')
                if p.is_file() and p.stat().st_size > 16 * 1024 * 1024:
                    raise ValueError('Unexpected large file in config backup')
                if p.is_file():
                    total_bytes += p.stat().st_size
                    if total_bytes > 64 * 1024 * 1024:
                        raise ValueError('Uncompressed configuration backup exceeds 64 MiB')
            tar.add(source, arcname=name)
    if stream.tell() > 256 * 1024 * 1024:
        raise ValueError('Backup too large')
    output.parent.mkdir(parents=True, exist_ok=True)
    # age refuses to overwrite existing output and handles all cryptography.
    r = subprocess.run([str(age), '-r', recipient, '-o', str(output)], input=stream.getvalue(), capture_output=True, timeout=120)
    if r.returncode:
        if output.exists():
            output.unlink()
        raise RuntimeError('age encryption failed; output suppressed')
    os.chmod(output, 0o600)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def restore(backup_path, identity, target, age):
    target = validate_state(target, ROOT)
    if target.exists():
        raise ValueError('Restore target must not exist')
    r = subprocess.run([str(age), '-d', '-i', str(identity), str(backup_path)], capture_output=True, timeout=120)
    if r.returncode:
        raise RuntimeError('age decryption failed; no restore performed')
    extract_safe(io.BytesIO(r.stdout), target)
    if (target / 'subscription').exists():
        from .subscription import runtime_permissions
        runtime_permissions(target)
    # Windows ACLs and Linux runtime ownership must be re-established on the destination.
    for release in (target / 'releases').glob('*') if (target / 'releases').exists() else []:
        secure_runtime(release)
    if os.name != 'nt' and (target / 'certs/live').exists():
        os.chmod(target / 'certs/live', 0o755)
        for p in (target / 'certs/live').iterdir():
            if p.is_file():
                os.chown(p, 10001, 10001)
                os.chmod(p, 0o400)
