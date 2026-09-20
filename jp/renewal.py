"""Explicit certificate replacement and reload; no undocumented hot reload."""
import os
import shutil
import tempfile
from pathlib import Path
from .common import read_json, run, write_private
from .certificates import check_pair, install_pair


def replace_and_reload(state, cert, key, domain):
    from .operations import prod_context, validate_release
    state = Path(state)
    check_pair(cert, key, domain)
    live = state / 'certs/live'
    active_file = state / 'active.json'
    if not active_file.exists():
        install_pair(state, cert, key, domain)
        return
    active = read_json(active_file)['current']
    current_domain = read_json(state / 'releases' / active / 'settings.json')['domain']
    if domain != current_domain:
        raise ValueError('Renewal domain differs from active release')
    if (live / 'server.crt').read_bytes() == Path(cert).read_bytes() and (live / 'server.key').read_bytes() == Path(key).read_bytes():
        return
    args, env = prod_context(state, active)
    # Keep a known-valid copy. Copy both files while stopped to avoid a mismatched pair.
    previous = state / 'certs/previous'
    previous.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('server.crt', 'server.key'):
        shutil.copy2(live / name, previous / name)
    run(args + ['stop', 'mihomo'], env=env)
    try:
        install_pair(state, cert, key, domain)
        validate_release(state, active)
        run(args + ['up', '-d', '--wait', '--wait-timeout', '75', 'mihomo'], env=env)
    except Exception:
        run(args + ['stop', 'mihomo'], env=env, check=False)
        try:
            install_pair(state, previous / 'server.crt', previous / 'server.key', domain)
            run(args + ['up', '-d', '--wait', '--wait-timeout', '75', 'mihomo'], env=env)
        except Exception:
            raise RuntimeError('Certificate load failed AND recovery failed; service stopped, inspect locally') from None
        raise RuntimeError('Certificate load failed; previous valid certificate restored') from None
    write_private(state / 'acceptance-pending.json', {'release': active, 'status': 'new certificate loaded; real client TLS/QUIC verification required'})
