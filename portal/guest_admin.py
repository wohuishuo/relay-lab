"""Open the separate guest site's loopback admin over a forwarding-only SSH key."""
import atexit
import os
import socket
import subprocess
import threading
import time

from django.conf import settings
from .maintenance import _tunnel

_lock = threading.Lock()
_process = None


def _stop():
    global _process
    if _process and _process.poll() is None:
        _process.terminate()
    _process = None


atexit.register(_stop)


def connect():
    global _process
    cfg = settings.CONFIG["public_guest"]
    with _lock:
        if _process and _process.poll() is None:
            return True
        listener = socket.socket()
        peers = []
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 18769))
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(15)
            opts = ["ssh", "-N", "-F", "NUL" if os.name == "nt" else "/dev/null",
                    "-o", "ExitOnForwardFailure=yes", "-o", "StrictHostKeyChecking=yes", "-o", "BatchMode=yes",
                    "-o", "HostKeyAlgorithms=ssh-ed25519", "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=10",
                    "-o", "ServerAliveInterval=20", "-o", "ServerAliveCountMax=2", "-o", "HostKeyAlias="+cfg["ssh_host"],
                    "-o", "UserKnownHostsFile="+cfg["known_hosts"], "-i", cfg["identity"],
                    "-p", str(listener.getsockname()[1]), "-L", "127.0.0.1:18769:127.0.0.1:18766",
                    "relay-guest-admin@127.0.0.1"]
            _process = proc = subprocess.Popen(opts, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            def serve():
                try:
                    _tunnel(listener, cfg["ssh_host"], settings.CONFIG["owner_proxy_port"], peers)
                finally:
                    listener.close()
                    for peer in peers:
                        peer.close()
            threading.Thread(target=serve, daemon=True).start()
            # Only redirect when the forwarding process owns a working remote admin.
            for _ in range(50):
                if proc.poll() is not None:
                    return False
                try:
                    with socket.create_connection(("127.0.0.1",18769),timeout=.4) as conn:
                        conn.settimeout(2)
                        conn.sendall(b"HEAD /admin/login/ HTTP/1.1\r\nHost: localhost:18769\r\nConnection: close\r\n\r\n")
                        if conn.recv(128).startswith(b"HTTP/1.1 200"):
                            return proc.poll() is None
                except OSError:
                    pass
                time.sleep(.2)
            _stop()
        except OSError:
            _stop()
            listener.close()
        return False
