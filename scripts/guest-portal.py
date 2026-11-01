#!/usr/bin/env python3
"""Bootstrap or run the independent guest website and its loopback-only Mihomo backend."""

import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jp.common import private_directory, write_private, state_lock, openssl
from jp.config import PRIVATE_V4, PRIVATE_V6, validate_state


def prepare(state, args):
    from django.core.management.utils import get_random_secret_key

    marker = state / "initializing"
    if not marker.exists():
        if any(path.name != ".operation.lock" for path in state.iterdir()):
            raise ValueError("Initialize an empty private directory")
        write_private(marker, {"origin": args.origin, "core_port": args.core_port})
    if json.loads(marker.read_text()) != {"origin": args.origin, "core_port": args.core_port}:
        raise ValueError("Resume with the original settings")
    if not (state / "settings.json").exists():
        cfg = {
            "origin": args.origin,
            "core_port": args.core_port,
            "secret": get_random_secret_key(),
            "guest_uuid": str(uuid.uuid4()),
        }
        from urllib.parse import urlsplit

        dest = urlsplit(args.origin)
        if (
            (
                dest.scheme != "https"
                and not (dest.scheme == "http" and dest.hostname in ("127.0.0.1", "localhost"))
            )
            or not dest.hostname
            or dest.username
            or dest.password
            or dest.query
            or dest.fragment
            or dest.path not in ("", "/")
        ):
            raise ValueError("Use a dedicated HTTPS origin or an HTTP loopback origin")
        if not 1024 <= args.core_port <= 65535:
            raise ValueError("Use an unprivileged guest port")
        tls = private_directory(state / "core-state")
        subprocess.run(
            [
                openssl(),
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-sha256",
                "-days",
                "365",
                "-subj",
                "/CN=relay-guest.internal",
                "-addext",
                "subjectAltName=DNS:relay-guest.internal,IP:127.0.0.1",
                "-keyout",
                str(tls / "loopback.key"),
                "-out",
                str(tls / "loopback.crt"),
            ],
            check=True,
            capture_output=True,
        )
        os.chmod(tls / "loopback.key", 0o600)
        os.chmod(tls / "loopback.crt", 0o600)
        rules = [f"IP-CIDR,{net},REJECT" for net in PRIVATE_V4]
        rules += [f"IP-CIDR6,{net},REJECT" for net in (*PRIVATE_V6, "::/0")]
        rules += ["DST-PORT,80,DIRECT", "DST-PORT,443,DIRECT", "MATCH,REJECT"]
        write_private(
            state / "guest-core.json",
            {
                "mode": "rule",
                "log-level": "silent",
                "ipv6": False,
                "listeners": [
                    {
                        "name": "guest-only",
                        "type": "vless",
                        "listen": "127.0.0.1",
                        "port": args.core_port,
                        "certificate": str(tls / "loopback.crt"),
                        "private-key": str(tls / "loopback.key"),
                        "users": [{"username": "guest-backend", "uuid": cfg["guest_uuid"]}],
                    }
                ],
                "rules": ["NETWORK,UDP,REJECT"] + rules,
            },
        )
        write_private(state / "settings.json", cfg)
    import django

    django.setup()
    from django.core.management import call_command
    from django.contrib.auth import get_user_model

    call_command("migrate", interactive=False, verbosity=0)
    call_command("collectstatic", interactive=False, verbosity=0)
    login = state / "owner-login.txt"
    if not login.exists():
        write_private(login, "owner\n" + secrets.token_urlsafe(24) + "\n")
    if not get_user_model().objects.filter(username="owner").exists():
        get_user_model().objects.create_superuser("owner", password=login.read_text().splitlines()[1])
    marker.unlink()
    print("Initialized. Owner login is in the private state directory.")


def serve(state, args):
    import uvicorn
    from django.conf import settings
    from portal.gateway import application

    if (state / "initializing").exists():
        raise ValueError("Resume initialization before serving")
    binpath = Path(args.core).resolve(strict=True)
    config = str(state / "guest-core.json")
    if not 1024 <= args.port <= 65535 or args.port == settings.CONFIG["core_port"]:
        raise ValueError("Invalid web port")
    if args.open:
        if not settings.LOCAL:
            raise ValueError("Desktop launcher requires a local instance")

        def open_when_ready():
            from urllib.request import build_opener, ProxyHandler

            url = f"http://127.0.0.1:{args.port}/"
            direct = build_opener(ProxyHandler({}))
            for _ in range(60):
                try:
                    with direct.open(url, timeout=0.5) as resp:
                        if b"RelayLab" in resp.read(8192):
                            webbrowser.open(url + "owner/")
                            return True
                except OSError:
                    time.sleep(0.15)
            return False

        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", args.port)) == 0:
                if not open_when_ready():
                    raise RuntimeError("Port belongs to another application")
                return
        threading.Thread(target=open_when_ready, daemon=True).start()
    with state_lock(state):
        ver = subprocess.run([binpath, "-v"], capture_output=True, timeout=8, check=True).stdout.decode()
        if "v1.19.33 " not in ver:
            raise ValueError("Expected the project-pinned Mihomo v1.19.33 binary")
        data = private_directory(state / "core-state")
        command = [str(binpath), "-d", str(data), "-f", config]
        subprocess.run(command + ["-t"], capture_output=True, timeout=12, check=True)
        with socket.socket() as s:
            s.bind(("127.0.0.1", settings.CONFIG["core_port"]))
        child = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                if child.poll() is not None:
                    raise RuntimeError("Guest core failed to start")
                try:
                    with socket.create_connection(("127.0.0.1", settings.CONFIG["core_port"]), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Guest core listener not ready")
            uvicorn.run(
                application,
                host="127.0.0.1",
                port=args.port,
                log_level="critical",
                access_log=False,
                lifespan="off",
                ws="websockets-sansio",
                ws_max_size=131072,
                ws_per_message_deflate=False,
                proxy_headers=False,
                limit_concurrency=100,
            )
        finally:
            child.terminate()
            child.wait(timeout=10)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", required=True, type=Path)
    commands = p.add_subparsers(dest="cmd", required=True)
    init = commands.add_parser("init")
    init.add_argument("--origin", default="http://127.0.0.1:18766")
    init.add_argument("--core-port", type=int, default=18767)
    serve_parser = commands.add_parser("serve")
    serve_parser.add_argument("--core", required=True)
    serve_parser.add_argument("--port", type=int, default=18766)
    serve_parser.add_argument(
        "--open", action="store_true", help="Open the local owner website in the default browser"
    )
    args = p.parse_args()
    state = private_directory(validate_state(args.state, ROOT))
    os.environ.update(RELAY_PORTAL_STATE=str(state), DJANGO_SETTINGS_MODULE="portal.settings")
    if args.cmd == "init":
        with state_lock(state):
            prepare(state, args)
    else:
        serve(state, args)


if __name__ == "__main__":
    main()
