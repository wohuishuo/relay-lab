"""Bounded operational counters. No requests, URLs, peers, credentials or packet payloads."""
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess


def container_summary(item):
    state = item.get('State', {})
    return {'name': str(item.get('Name', '')).lstrip('/')[:80],
            'running': bool(state.get('Running')), 'oom_killed': bool(state.get('OOMKilled')),
            'restarts': int(item.get('RestartCount', 0)),
            'health': str(state.get('Health', {}).get('Status', 'not-configured'))[:24],
            'started': str(state.get('StartedAt', ''))[:40]}


def append_bounded(directory, record, *, max_bytes=2 * 1024 * 1024, files=5):
    directory = Path(directory)
    if files < 1 or files > 20 or max_bytes < 128:
        raise ValueError('Invalid retention bounds')
    data = (json.dumps(record, separators=(',', ':')) + '\n').encode()
    if len(data) > max_bytes:
        raise ValueError('Snapshot exceeds a complete log segment')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    paths = [directory / ('metrics.jsonl' if i == 0 else f'metrics.{i}.jsonl') for i in range(files)]
    if any(p.is_symlink() for p in paths):
        raise ValueError('Metrics logs must not be symlinks')
    if paths[0].exists() and paths[0].stat().st_size + len(data) > max_bytes:
        paths[-1].unlink(missing_ok=True)
        for i in range(files - 2, -1, -1):
            if paths[i].exists():
                os.replace(paths[i], paths[i + 1])
    with paths[0].open('ab') as stream:
        stream.write(data)
    os.chmod(paths[0], 0o600)


def _command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError('Metric collection command failed; output suppressed')
    return result.stdout


def _proc(pid):
    root = Path('/proc') / str(pid)
    result = {}
    try:
        for line in (root / 'status').read_text().splitlines():
            key, _, value = line.partition(':')
            if key in ('VmRSS', 'VmSwap'):
                result[key.lower() + '_bytes'] = int(value.split()[0]) * 1024
            elif key == 'Threads':
                result['threads'] = int(value)
        result['fds'] = sum(1 for _ in (root / 'fd').iterdir())
    except (OSError, ValueError):
        result['proc_sample_unavailable'] = True
    return result


def _container_resources(pid):
    result = {'processes': []}
    pending, seen = [pid], set()
    while pending and len(seen) < 16:
        child = pending.pop()
        if child in seen:
            continue
        seen.add(child)
        root = Path('/proc') / str(child)
        try:
            name = (root / 'comm').read_text().strip()[:40]
            result['processes'].append({'name': name, **_proc(child)})
            pending.extend(int(n) for n in (root / 'task' / str(child) / 'children').read_text().split())
        except (OSError, ValueError):
            pass
    try:
        group = next(line[3:] for line in (Path('/proc') / str(pid) / 'cgroup').read_text().splitlines()
                     if line.startswith('0::'))
        root = Path('/sys/fs/cgroup').resolve()
        path = (root / group.lstrip('/')).resolve()
        if path.is_relative_to(root):
            result['cgroup_memory_bytes'] = int((path / 'memory.current').read_text())
            result['memory_events'] = {key: int(value) for key, value in
                                       (line.split() for line in (path / 'memory.events').read_text().splitlines())}
    except (OSError, ValueError, StopIteration):
        result['cgroup_sample_unavailable'] = True
    return result


def collect():
    if os.name != 'posix':
        raise RuntimeError('Linux host metrics only')
    result = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'containers': []}
    lines = _command(['docker', 'ps', '-a', '--format', '{{.ID}} {{.Names}}']).splitlines()
    ids = [line.split()[0] for line in lines if len(line.split()) == 2 and
           line.split()[1].startswith(('jp-proxy-', 'jp-subscription-', 'jp-ss-shadowtls-'))]
    if ids:
        for item in json.loads(_command(['docker', 'inspect', *ids])):
            summary = container_summary(item)
            if item.get('State', {}).get('Pid', 0) > 0:
                summary.update(_container_resources(item['State']['Pid']))
            result['containers'].append(summary)
    mem = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
            mem[key + '_bytes'] = int(value.split()[0]) * 1024
    result['memory'] = mem
    result['load'] = list(os.getloadavg())
    disk = shutil.disk_usage('/')
    result['disk'] = {'total_bytes': disk.total, 'free_bytes': disk.free}
    result['uptime_seconds'] = float(Path('/proc/uptime').read_text().split()[0])
    result['network'] = {}
    for interface in Path('/sys/class/net').iterdir():
        if interface.name.startswith(('eth', 'en')):
            result['network'][interface.name] = {
                name: int((interface / 'statistics' / name).read_text())
                for name in ('rx_bytes', 'tx_bytes', 'rx_dropped', 'tx_dropped')}
    for name in ('nf_conntrack_count', 'nf_conntrack_max'):
        path = Path('/proc/sys/net/netfilter') / name
        if path.exists():
            result[name] = int(path.read_text())
    return result
