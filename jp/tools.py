"""Fetch only explicitly locked upstream utility assets; verify before extraction."""
import hashlib
import io
import os
import platform
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from .common import ROOT, private_directory, read_json


def read_binary(archive, filename, system):
    if system == 'windows':
        members = [m for m in archive.infolist()
                   if not m.is_dir() and Path(m.filename).name == filename]
    else:
        members = [m for m in archive.getmembers()
                   if m.isfile() and Path(m.name).name == filename]
    if len(members) != 1:
        raise ValueError('Expected exactly one regular executable in utility archive')
    if system == 'windows':
        return archive.read(members[0])
    with archive.extractfile(members[0]) as stream:
        return stream.read()


def install_tools(directory, names=('age', 'lego')):
    directory = private_directory(directory)
    if platform.machine().lower() not in ('amd64', 'x86_64'):
        raise ValueError('This lock file supports amd64 only')
    system = 'windows' if os.name == 'nt' else 'linux'
    suffix = '.exe' if os.name == 'nt' else ''
    lock = read_json(ROOT / 'versions.lock.json')['tools']
    for name in names:
        entry = lock[name][system]
        data = urllib.request.urlopen(entry['url'], timeout=90).read()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Upstream utility SHA256 mismatch')
        binaries = [name, 'age-keygen'] if name == 'age' else [name]
        archive = zipfile.ZipFile(io.BytesIO(data)) if system == 'windows' else tarfile.open(fileobj=io.BytesIO(data), mode='r:gz')
        try:
            for binary in binaries:
                content = read_binary(archive, binary + suffix, system)
                path = directory / (binary + suffix)
                path.write_bytes(content)
                os.chmod(path, 0o700)
        finally:
            archive.close()
    return directory
