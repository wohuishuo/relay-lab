"""Fresh-host plan and fail-stop installation. No SSH/firewall modification."""
import os
import platform
from pathlib import Path
from .common import ROOT, read_json, run, write_private
from .config import example_secrets, server_config, validate_host, validate_state, PORTS


def plan(settings, state):
    state = validate_state(state, ROOT)
    if (state / 'active.json').exists() or (state / 'releases').exists():
        raise ValueError('Existing deployment detected; use the release workflow instead')
    validate_host(settings['server'])
    server_config(settings['protocols'], example_secrets(), settings['domain'],
                  settings['reality_dest'], settings['reality_sni'])
    for value in (settings['server'], settings['domain'], settings['reality_sni'], settings['reality_dest'].split(':')[0]):
        if value in ('example.com', 'example.org') or value.endswith(('.example.com', '.example.org')):
            raise ValueError('Replace example hosts before planning installation')
    return {'mode': 'plan-only', 'protocols': settings['protocols'],
            'inbound': [{'protocol': transport, 'port': PORTS[p][0]} for p in settings['protocols'] for transport in PORTS[p][2]],
            'steps': ['check fresh Ubuntu host and Docker', 'pull pinned images', 'install hash-verified tools',
                      'ACME staging', 'ACME production', 'prepare private release', 'validate and deploy',
                      'export private client', 'enable certificate renewal timer'],
            'external_acceptance': 'required after installation', 'changes_ssh_or_firewall': False}


def apply(settings, state, email, credentials, *, firewall_ready=False, recovery_ready=False, accept_acme_tos=False):
    plan(settings, state)
    state = Path(state).resolve()
    credentials_input = Path(credentials)
    credentials = credentials_input.resolve()
    if not all((firewall_ready, recovery_ready, accept_acme_tos)):
        raise ValueError('Confirm firewall, recovery console, and ACME terms before --apply')
    if os.name != 'posix' or os.geteuid() != 0 or platform.machine() not in ('x86_64', 'AMD64'):
        raise ValueError('Apply requires root on Ubuntu 24.04 amd64')
    if ROOT != Path('/opt/relay-lab') or state != Path('/var/lib/relay-lab'):
        raise ValueError('Apply requires source /opt/relay-lab and state /var/lib/relay-lab')
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if release.get('ID', '').strip('"') != 'ubuntu' or release.get('VERSION_ID', '').strip('"') != '24.04':
        raise ValueError('Only Ubuntu 24.04 is supported by this installer')
    validate_state(credentials, ROOT)
    if credentials_input.is_symlink() or not credentials.is_file() or credentials.stat().st_mode & 0o077:
        raise ValueError('DNS credential file must be a regular private file (mode 600)')
    if '\n' in email or '@' not in email:
        raise ValueError('A contact email is required')
    run(['docker', 'compose', 'version'])
    occupied = run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=jp-proxy']).stdout.strip()
    if occupied:
        raise ValueError('An existing proxy Compose project exists; refusing to replace it')
    return install_steps(settings, state, email, credentials)


def install_steps(settings, state, email, credentials):
    """Called only after preflight with the state lock held; separable for failure tests."""
    # Every step is synchronous, checked, and stops at first error. No automatic retry deploy.
    from .common import image
    from .tools import install_tools
    from .certificates import acme, install_pair
    for name in ('mihomo', 'mihomo_previous', 'python'):
        run(['docker', 'pull', '--platform', 'linux/amd64', image(name)], timeout=300)
    tools_dir = '/opt/relay-lab-tools'
    install_tools(tools_dir)
    acme(state, settings['domain'], email, 'cloudflare', credentials, tools_dir + '/lego', staging=True)
    cert, key = acme(state, settings['domain'], email, 'cloudflare', credentials, tools_dir + '/lego')
    install_pair(state, cert, key, settings['domain'])
    from .operations import prepare, deploy
    from .bundle import bundle
    release_id = prepare(state, settings)
    deploy(state, release_id)
    clients = {p: read_json(state / 'releases' / release_id / 'clients' / (p + '.yaml')) for p in settings['protocols']}
    write_private(state / 'client.yaml', bundle(clients))
    write_private(state / 'renewal.json', {'domain': settings['domain'], 'email': email,
                                         'credentials': str(credentials), 'lego': tools_dir + '/lego'})
    service = '[Unit]\nDescription=personal proxy certificate renewal\nAfter=docker.service network-online.target\nWants=network-online.target\n\n[Service]\nType=oneshot\nUMask=0077\nExecStart=/usr/bin/python3 /opt/relay-lab/scripts/renew.py\n'
    timer = '[Unit]\nDescription=Check personal proxy certificate twice daily\n\n[Timer]\nOnCalendar=*-*-* 00,12:00:00\nRandomizedDelaySec=30m\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n'
    write_private('/etc/systemd/system/relay-lab-renew.service', service)
    write_private('/etc/systemd/system/relay-lab-renew.timer', timer)
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'enable', '--now', 'relay-lab-renew.timer'])
    return release_id
