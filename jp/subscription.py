"""Token-protected static HTTPS via pinned upstream Caddy. No custom TLS or HTTP server."""
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
from urllib.parse import urlsplit

from .common import ROOT, image, private_directory, read_json, run, write_private
from .config import validate_domain, validate_state


def runtime_permissions(state):
    for name in ('runtime', 'www'):
        folder = Path(state) / 'subscription' / name
        if not folder.exists():
            continue
        for path in [folder] + list(folder.iterdir()):
            if os.name != 'nt':
                os.chown(path, 10001, 10001)
                os.chmod(path, 0o500 if path.is_dir() else 0o400)
            else:
                # Parent Windows ACL is private. A DOS read-only bit prevents
                # atomic replacement during publication or token rotation.
                os.chmod(path, 0o700 if path.is_dir() else 0o600)


def client_bytes(client):
    payload = Path(client).read_bytes()
    cfg = json.loads(payload)
    if not cfg.get('proxies') or not cfg.get('rules'):
        raise ValueError('Use a complete exported JSON/YAML client configuration')
    if any(p.get('skip-cert-verify') for p in cfg['proxies']):
        raise ValueError('TLS verification must remain enabled')
    return payload


def prepare(state, client, domain, *, port=2087, bind='127.0.0.1'):
    state = validate_state(state, ROOT)
    domain = validate_domain(domain)
    if not 1024 <= port <= 65535 or ipaddress.ip_address(bind).version != 4:
        raise ValueError('Use an IPv4 bind address and unprivileged TCP port')
    payload = client_bytes(client)
    dest = state / 'subscription'
    if dest.exists():
        raise ValueError('Subscription already exists; publish updates without changing its URL')
    private_directory(dest)
    token = secrets.token_urlsafe(32)
    route = '/sub/' + token + '/config.yaml'
    config = '''{
    admin off
    persist_config off
    auto_https off
    log {
        output discard
    }
    servers {
        protocols h1 h2
    }
}
https://DOMAIN:2087 {
    tls /certs/server.crt /certs/server.key
    @authorized {
        path ROUTE
        method GET
    }
    handle @authorized {
        header Cache-Control "no-store"
        header Content-Type "text/yaml; charset=utf-8"
        header Referrer-Policy "no-referrer"
        rewrite * /config.yaml
        root * /srv
        file_server
    }
    handle {
        respond "Not found" 404
    }
}
'''.replace('DOMAIN', domain).replace('ROUTE', route)
    write_private(dest / 'settings.json', {'domain': domain, 'port': port, 'bind': bind})
    write_private(dest / 'url.txt', f'https://{domain}:{port}{route}\n')
    write_private(dest / 'runtime/Caddyfile', config)
    write_private(dest / 'www/config.yaml', payload.decode('utf-8'))
    runtime_permissions(state)


def compose(state):
    state = Path(state).resolve()
    cfg = read_json(state / 'subscription/settings.json')
    env = os.environ.copy()
    env.update(JP_SUB_STATE=str(state), JP_SUB_IMAGE=image('caddy'),
               JP_SUB_BIND=cfg['bind'], JP_SUB_PORT=str(cfg['port']))
    project = 'jp-subscription-' + hashlib.sha256(str(state).encode()).hexdigest()[:8]
    return ['docker', 'compose', '-p', project, '-f', str(ROOT / 'compose.subscription.yaml')], env


def fetch(url, *, ca=None, resolve=None, method='GET'):
    """Use standard-library verified TLS; never emit URL or response in errors."""
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('A plain HTTPS subscription URL is required')
    context = ssl.create_default_context(cafile=str(ca) if ca else None)
    conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, context=context, timeout=20)
    try:
        if resolve:
            raw = socket.create_connection((resolve, parsed.port or 443), timeout=20)
            try:
                conn.sock = context.wrap_socket(raw, server_hostname=parsed.hostname)
            except Exception:
                raw.close()
                raise
        path = (parsed.path or '/') + ('?' + parsed.query if parsed.query else '')
        conn.request(method, path)
        response = conn.getresponse()
        body = response.read(2 * 1024 * 1024 + 1)
        if len(body) > 2 * 1024 * 1024:
            raise ValueError('Response too large')
        return response.status, body
    except Exception:
        raise RuntimeError('HTTPS subscription request failed; URL and response suppressed') from None
    finally:
        conn.close()


def check(state, *, ca=None, public=False):
    dest = Path(state) / 'subscription'
    url = (dest / 'url.txt').read_text(encoding='utf-8').strip()
    kwargs = {'ca': ca, 'resolve': None if public else '127.0.0.1'}
    status, body = fetch(url, **kwargs)
    if status != 200 or json.loads(body) != read_json(dest / 'www/config.yaml'):
        raise RuntimeError('Subscription content verification failed')
    parsed = urlsplit(url)
    for path in ('/', '/config.yaml', '/sub/incorrect/config.yaml'):
        status, body = fetch(f'https://{parsed.netloc}{path}', **kwargs)
        if status != 404 or body != b'Not found':
            raise RuntimeError('Unauthenticated subscription access was not rejected')


def deploy(state, *, ca=None):
    args, env = compose(state)
    runtime_permissions(state)
    run(args + ['run', '--rm', '--no-deps', '-T', 'subscription', 'caddy',
                'validate', '--config', '/config/Caddyfile', '--adapter', 'caddyfile'], env=env)
    try:
        run(args + ['up', '-d', '--force-recreate', '--wait', '--wait-timeout', '45'], env=env)
        check(state, ca=ca)
    except Exception:
        run(args + ['stop'], env=env, check=False)
        raise RuntimeError('Subscription deployment failed and was stopped; proxy core unchanged') from None
    digest = hashlib.sha256((Path(state) / 'certs/live/server.crt').read_bytes()).hexdigest()
    write_private(Path(state) / 'subscription/loaded-cert.sha256', digest)


def refresh_certificate(state):
    dest = Path(state) / 'subscription'
    digest = hashlib.sha256((Path(state) / 'certs/live/server.crt').read_bytes()).hexdigest()
    marker = dest / 'loaded-cert.sha256'
    if not marker.exists() or marker.read_text() != digest:
        deploy(state)


def publish(state, client):
    payload = client_bytes(client).decode('utf-8')
    dest = Path(state) / 'subscription/www/config.yaml'
    previous = dest.read_text(encoding='utf-8')
    write_private(dest, payload)
    runtime_permissions(state)
    try:
        check(state)
    except Exception:
        write_private(dest, previous)
        runtime_permissions(state)
        raise RuntimeError('Subscription update failed; previous content restored') from None


def rotate(state, *, ca=None):
    dest = Path(state) / 'subscription'
    old_url = (dest / 'url.txt').read_text(encoding='utf-8').strip()
    old_path = urlsplit(old_url).path
    new_path = '/sub/' + secrets.token_urlsafe(32) + '/config.yaml'
    file = dest / 'runtime/Caddyfile'
    content = file.read_text(encoding='utf-8')
    if content.count(old_path) != 1:
        raise ValueError('Subscription route does not match private URL')
    stop(state)
    write_private(file, content.replace(old_path, new_path))
    parsed = urlsplit(old_url)
    write_private(dest / 'url.txt', f'https://{parsed.netloc}{new_path}\n')
    runtime_permissions(state)
    # Failure leaves service stopped. Never silently restore a revoked URL.
    deploy(state, ca=ca)


def stop(state, *, remove=False):
    args, env = compose(state)
    run(args + (['down'] if remove else ['stop']), env=env)
