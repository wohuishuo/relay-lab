import json
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_private(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(data if isinstance(data, str) else json.dumps(data, indent=2) + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run(args, *, timeout=120, env=None, check=True, input=None, cwd=None):
    """Capture output; callers must opt in to displaying sanitized output."""
    try:
        r = subprocess.run([str(a) for a in args], input=input, capture_output=True,
                           text=True, encoding='utf-8', errors='replace', timeout=timeout,
                           env=env, cwd=cwd)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'{Path(str(args[0])).name} timed out; no success recorded') from None
    if check and r.returncode:
        # Upstream parser errors can contain entire credentials. Do not print them.
        raise RuntimeError(f'{Path(str(args[0])).name} failed (exit {r.returncode}); output suppressed to protect secrets')
    return r


def image(name='mihomo'):
    obj = read_json(ROOT / 'versions.lock.json')['images'][name]
    return 'docker.io/' + obj['repository'] + '@' + obj['digest']


def openssl():
    executable = os.environ.get('JP_OPENSSL') or shutil.which('openssl')
    if not executable and os.name == 'nt':
        candidate = Path.home() / 'scoop/apps/git/current/usr/bin/openssl.exe'
        if candidate.exists():
            executable = str(candidate)
    if not executable:
        raise RuntimeError('OpenSSL is required; set JP_OPENSSL or install the OS package')
    return executable


def docker_available():
    run(['docker', 'info', '--format', '{{.ServerVersion}}'], timeout=30)


def private_directory(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == 'nt':
        import getpass
        run(['icacls', str(path), '/inheritance:r', '/grant:r', getpass.getuser() + ':(OI)(CI)F'], timeout=20)
    else:
        os.chmod(path, 0o700)
    return path


@contextmanager
def state_lock(state):
    """OS-held advisory lock survives crashes without a stale lock condition."""
    state = private_directory(state)
    with open(state / '.operation.lock', 'a+b') as lock:
        lock.seek(0)
        if os.fstat(lock.fileno()).st_size == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Another operation is using this state directory') from None
        try:
            yield
        finally:
            if os.name == 'nt':
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
