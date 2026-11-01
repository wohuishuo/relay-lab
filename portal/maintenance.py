"""Owner-only serial maintenance transport. Public guest installations never configure this adapter."""

import base64
import json
import os
import re
import secrets
import socket
import subprocess
import threading
import time
import zlib
from pathlib import Path

from django.conf import settings

LOCK = threading.Lock()
ACTIONS = {"status", "restart", "update"}


def _forward(src, dst):
    try:
        while data := src.recv(32768):
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def _tunnel(listener, gateway, proxy_port, connections):
    try:
        local, _ = listener.accept()
        connections.append(local)
        remote = socket.create_connection(("127.0.0.1", proxy_port), timeout=8)
        connections.append(remote)
        remote.sendall(f"CONNECT {gateway}:22 HTTP/1.1\r\nHost: {gateway}:22\r\n\r\n".encode())
        header = b""
        while len(header) < 8192 and not header.endswith(b"\r\n\r\n"):
            part = remote.recv(1)
            if not part:
                return
            header += part
        if not re.match(rb"HTTP/1\.[01] 200 ", header):
            return
        remote.settimeout(None)
        threading.Thread(target=_forward, args=(local, remote), daemon=True).start()
        _forward(remote, local)
    except OSError:
        pass


def command(action):
    if action not in ACTIONS or not settings.LOCAL:
        raise ValueError("Unsupported operation")
    cfg = settings.CONFIG["maintenance"]
    if not LOCK.acquire(blocking=False):
        return {"result": "busy"}
    listener = socket.socket()
    connections = []
    proc = None
    try:
        gateway = cfg["gateway"]
        if not re.fullmatch(r"[a-z0-9.-]+", gateway) or not all(
            re.fullmatch(r"[A-Za-z0-9_-]+", cfg[k]) for k in ("user", "instance")
        ):
            raise ValueError("Invalid management configuration")
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(10)
        threading.Thread(
            target=_tunnel,
            args=(listener, gateway, settings.CONFIG["owner_proxy_port"], connections),
            daemon=True,
        ).start()
        args = [
            "ssh",
            "-F",
            "NUL" if os.name == "nt" else "/dev/null",
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "HostKeyAlias=" + gateway,
            "-o",
            "UserKnownHostsFile=" + cfg["known_hosts"],
            "-o",
            "HostKeyAlgorithms=ecdsa-sha2-nistp256",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "EscapeChar=none",
            "-i",
            cfg["identity"],
            "-p",
            str(listener.getsockname()[1]),
            "-tt",
            cfg["user"] + "@127.0.0.1",
            cfg["instance"],
        ]
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            env=dict(os.environ, TERM="xterm"),
        )
        data = bytearray()
        mutex = threading.Lock()

        def read():
            while chunk := proc.stdout.read(4096):
                with mutex:
                    data.extend(chunk)
                    del data[:-32768]

        threading.Thread(target=read, daemon=True).start()

        def snapshot():
            with mutex:
                return bytes(data)

        time.sleep(1.5)
        proc.stdin.write(b"\n")
        # Require an idle shell prompt before sending even the identity check.
        for _ in range(100):
            clean = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", snapshot()).replace(b"\r", b"")
            if re.search(rb"(?:^|\n)root@[\w.-]+:[^\n]{0,160}#\s*$", clean):
                break
            if proc.poll() is not None:
                return {"result": "unreachable"}
            if _ in (12, 30):
                proc.stdin.write(b"\n")
            time.sleep(0.2)
        else:
            return {"result": "no_shell"}
        fingerprint = cfg["guest_fingerprint"]
        if not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", fingerprint):
            raise ValueError("Invalid guest fingerprint")
        pin = json.loads((Path(__file__).resolve().parents[1] / "versions.lock.json").read_text())["images"][
            "mihomo"
        ]["digest"]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", pin):
            raise ValueError("Invalid image pin")
        nonce = "RESULT_" + secrets.token_hex(12)
        code = (
            Path(__file__).with_name("node_action.py").read_text(encoding="utf-8")
            + "\nprint("
            + repr(nonce)
            + "+json.dumps(perform("
            + ",".join(map(repr, (action, fingerprint, pin)))
            + ")))"
        )
        blob = base64.b64encode(zlib.compress(code.encode())).decode("ascii")
        line = (
            "python3 -c \"import base64,zlib;exec(zlib.decompress(base64.b64decode('" + blob + "')))\"\n"
        ).encode()
        if len(line) > 3800:
            raise RuntimeError("Command exceeds serial frame")
        for pos in range(0, len(line), 96):
            proc.stdin.write(line[pos : pos + 96])
            time.sleep(0.05)
        for _ in range(65):
            match = re.search(rb"(?:^|[\r\n])" + nonce.encode() + rb"(\{[^\r\n]+\})", snapshot())
            if match:
                return json.loads(match[1])
            time.sleep(0.2)
        return {"result": "unknown"}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"result": "unreachable"}
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            proc.stdin.close()
            proc.stdout.close()
        listener.close()
        for sock in connections:
            sock.close()
        LOCK.release()
