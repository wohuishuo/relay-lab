#!/usr/bin/env python3
"""Use two real, isolated Mihomo processes and an HTTP fixture. No WAN, owner settings or credentials."""

import argparse
import concurrent.futures
import contextlib
from datetime import timedelta
import http.server
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jp.common import write_private


def unused():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait(port, proc):
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError("Isolated service exited")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.15):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Service readiness timeout")


class Target(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        n = int(self.path.strip("/"))
        self.send_response(200)
        self.send_header("Content-Length", str(n))
        self.end_headers()
        try:
            self.wfile.write(b"A" * n)
        except OSError:
            pass

    def log_message(self, *args):
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--core", required=True)
    args = p.parse_args()
    core = str(Path(args.core).resolve(strict=True))
    with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
        base = Path(tmp)
        state = base / "state"
        web, backend = unused(), unused()
        script = [sys.executable, str(ROOT / "scripts/guest-portal.py"), "--state", str(state)]
        subprocess.run(
            script + ["init", "--origin", f"https://127.0.0.1:{web}", "--core-port", str(backend)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        cert = state / "core-state" / "loopback.crt"
        target = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Target)
        target_port = target.server_address[1]
        threading.Thread(target=target.serve_forever, daemon=True).start()
        stack.callback(target.server_close)
        stack.callback(target.shutdown)
        cfg = json.loads((state / "guest-core.json").read_text())
        cfg["rules"].insert(0, f"AND,((IP-CIDR,127.0.0.1/32),(DST-PORT,{target_port})),DIRECT")
        write_private(state / "guest-core.json", cfg)

        def start(command):
            proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            def stop():
                proc.terminate()
                proc.wait(timeout=7)

            stack.callback(stop)
            return proc

        # Launch core and web separately so teardown is reliable even on Windows.
        proc = start([core, "-d", str(state), "-f", str(state / "guest-core.json")])
        wait(backend, proc)
        os.environ.update(RELAY_PORTAL_STATE=str(state), DJANGO_SETTINGS_MODULE="portal.settings")
        proc = start(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "portal.gateway:application",
                "--app-dir",
                str(ROOT),
                "--host",
                "127.0.0.1",
                "--port",
                str(web),
                "--no-access-log",
                "--log-level",
                "critical",
                "--lifespan",
                "off",
                "--ws",
                "websockets-sansio",
                "--ssl-certfile",
                str(cert),
                "--ssl-keyfile",
                str(state / "core-state" / "loopback.key"),
            ]
        )
        wait(web, proc)
        import django

        django.setup()
        from django.test import Client
        from django.utils import timezone
        from django.db import connections
        from portal.models import Pass, Plan, TRIAL_BYTES
        from django.contrib.auth import get_user_model

        stack.callback(connections.close_all)
        c = Client(enforce_csrf_checks=True, HTTP_HOST="127.0.0.1")
        assert c.get("/owner/").status_code == 302
        assert c.post("/apply/").status_code == 403
        login_path = "/admin/login/?next=/owner/"
        assert c.get(login_path)["Referrer-Policy"] == "same-origin"
        form = {"csrfmiddlewaretoken": c.cookies["csrftoken"].value, "username": "missing", "password": "invalid"}
        assert c.post(login_path, form, HTTP_ORIGIN="http://127.0.0.1").status_code == 200
        assert c.post(login_path, form, HTTP_ORIGIN="null").status_code == 403
        assert c.post(login_path, form, HTTP_ORIGIN="https://other.invalid").status_code == 403
        c.get("/register/")
        passwd = secrets.token_urlsafe(18)
        assert (
            c.post(
                "/register/",
                {
                    "csrfmiddlewaretoken": c.cookies["csrftoken"].value,
                    "username": "trial",
                    "password1": passwd,
                    "password2": passwd,
                },
            ).status_code
            == 302
        )

        def post(path, data):
            return c.post(path, {**data, "csrfmiddlewaretoken": c.cookies["csrftoken"].value})

        plan = Plan.objects.get()
        assert post("/apply/", {"plan": plan.pk}).status_code == 302
        assert post("/apply/", {"plan": plan.pk}).status_code == 302
        grant = Pass.objects.get()
        route = "/s/" + grant.token("subscription")
        assert c.get(route).status_code == 404 and c.get("/owner/").status_code == 302
        owner = get_user_model().objects.get(username="owner")
        c.force_login(owner)
        c.get("/admin/portal/pass/")
        assert (
            post(
                "/admin/portal/pass/", {"action": "approve", "_selected_action": str(grant.pk), "index": "0"}
            ).status_code
            == 302
        )
        grant.refresh_from_db()
        assert (
            71.99 < (grant.expires - timezone.now()).total_seconds() / 3600 <= 72
            and grant.limit == TRIAL_BYTES
        )
        subscription = c.get(route)
        assert subscription["Referrer-Policy"] == "no-referrer"
        profile = json.loads(subscription.content)
        assert profile["proxies"][0]["tls"]
        # The misspelled key is the actual v1.19.33 config tag. Trust only this lab CA.
        profile["tls"] = {"custom-certifactes": [cert.read_text()]}
        c.get("/owner/")
        first = c.session["issue_key"]
        result = post("/owner/", {"action": "issue", "issue_key": first, "plan": plan.pk})
        assert result.status_code == 302 and Pass.objects.filter(owner__isnull=True).count() == 1
        post("/owner/", {"action": "issue", "issue_key": first, "plan": plan.pk})
        assert Pass.objects.count() == 2
        port = unused()
        profile.update({"mixed-port": port, "log-level": "silent"})
        write_private(base / "client.json", profile)
        proc = start([core, "-d", str(base / "client"), "-f", str(base / "client.json")])
        wait(port, proc)

        def fetch(size):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
            try:
                conn.request("GET", f"http://127.0.0.1:{target_port}/{size}")
                r = conn.getresponse()
                return r.status == 200 and r.read() == b"A" * size
            except (OSError, http.client.HTTPException):
                return False
            finally:
                conn.close()

        assert fetch(2048), "valid real guest could not transfer"
        grant.refresh_from_db()
        assert grant.used >= 2048 and 0 < grant.uploaded < grant.used
        Pass.objects.filter(pk=grant.pk).update(limit=grant.used + 4096)
        assert not fetch(65536), "oversized transfer passed"
        grant.refresh_from_db()
        assert grant.used <= grant.limit and not fetch(20) and c.get(route).status_code == 404
        print(
            "PASS register, CSRF, owner approval, 72h / 10GB, real VLESS-WS transfer, quota and cached credential denial"
        )

        def reset():
            Pass.objects.filter(pk=grant.pk).update(
                status=Pass.Status.ACTIVE, limit=TRIAL_BYTES, expires=timezone.now() + timedelta(hours=1)
            )

        reset()
        assert fetch(32)
        import asyncio
        from websockets.asyncio.client import connect
        from websockets.exceptions import ConnectionClosed
        from asgiref.sync import sync_to_async

        async def cutoff(expire):
            async with connect(
                f"wss://127.0.0.1:{web}/connect",
                ssl=ssl.create_default_context(cafile=str(cert)),
                additional_headers={"Authorization": "Bearer " + grant.token("wire")},
                proxy=None,
            ) as ws:
                if expire:
                    await Pass.objects.filter(pk=grant.pk).aupdate(
                        expires=timezone.now() - timedelta(seconds=1)
                    )
                else:
                    await Pass.objects.filter(pk=grant.pk).aupdate(status=Pass.Status.REVOKED)
                try:
                    await asyncio.wait_for(ws.recv(), 3)
                except ConnectionClosed:
                    return
                raise AssertionError("Open credential survived cutoff")

        for expire in (True, False):
            reset()
            asyncio.run(cutoff(expire))
            assert not fetch(20) and c.get(route).status_code == 404
        reset()
        Pass.objects.filter(pk=grant.pk).update(used=0, limit=1000)

        def reserve(_):
            try:
                return Pass.charge(grant.pk, 100)
            finally:
                connections.close_all()

        with concurrent.futures.ThreadPoolExecutor(6) as pool:
            assert sum(pool.map(reserve, range(18))) == 10
        asyncio.run(sync_to_async(connections.close_all)())
        print(
            "PASS expiration and revocation close open WebSockets and reject cached profiles; 18 concurrent reservations cannot overdraw"
        )


if __name__ == "__main__":
    main()
