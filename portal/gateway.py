"""A metered byte bridge. Uvicorn handles WebSocket/TLS and Mihomo handles VLESS."""

import asyncio
import ssl
from contextlib import suppress
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import F
from django.utils import timezone
from django.core.asgi import get_asgi_application

django_app = get_asgi_application()
from .models import Pass

CHUNK = 32768
upstream_tls = ssl.create_default_context(cafile=str(settings.STATE / "core-state" / "loopback.crt"))


async def application(scope, receive, send):
    headers = dict(scope.get("headers", ()))
    if (
        not settings.LOCAL
        and headers.get(b"host", b"").decode("ascii", "replace").lower() == settings.ORIGIN.netloc.lower()
    ):
        public = (scope.get("client") or ("",))[0] in ("127.0.0.1", "::1") and headers.get(
            b"x-forwarded-proto"
        ) == b"https"
        blocked = scope["path"].startswith(("/admin", "/owner"))
        if not public or blocked:
            if scope["type"] == "http":
                await send({"type": "http.response.start", "status": 404, "headers": []})
                return await send({"type": "http.response.body", "body": b""})
            return await send({"type": "websocket.close", "code": 1008})
        scope = dict(scope, scheme="https" if scope["type"] == "http" else "wss")
    if scope["type"] == "http":
        return await django_app(scope, receive, send)
    if scope["type"] != "websocket":
        raise NotImplementedError
    await receive()
    auth = headers.get(b"authorization", b"")
    if (
        scope["path"] != "/connect"
        or len(auth) > 180
        or not auth.startswith(b"Bearer ")
        or headers.get(b"host", b"").decode("ascii", "replace").lower() != settings.ORIGIN.netloc.lower()
        or b"origin" in headers
        and headers[b"origin"].decode("ascii", "replace") != settings.BASE
    ):
        return await send({"type": "websocket.close", "code": 1008})
    grant = await sync_to_async(Pass.from_token)(auth[7:].decode("ascii", "replace"), "wire")
    if not grant:
        return await send({"type": "websocket.close", "code": 1008})
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                "127.0.0.1",
                settings.CONFIG["core_port"],
                ssl=upstream_tls,
                server_hostname="relay-guest.internal",
            ),
            3,
        )
    except (TimeoutError, OSError):
        return await send({"type": "websocket.close", "code": 1011})
    tasks = []
    charge = sync_to_async(Pass.charge)

    async def upload():
        while True:
            message = await receive()
            data = message.get("bytes")
            if data is None or message["type"] == "websocket.disconnect":
                return
            for pos in range(0, len(data), CHUNK):
                part = data[pos : pos + CHUNK]
                if not await charge(grant.pk, len(part), upload=True):
                    return
                writer.write(part)
                await writer.drain()

    async def download():
        while data := await reader.read(CHUNK):
            if not await charge(grant.pk, len(data)):
                return
            await send({"type": "websocket.send", "bytes": data})

    async def watchdog():
        while True:
            await asyncio.sleep(1)
            if not await Pass.objects.filter(
                pk=grant.pk, status=Pass.Status.ACTIVE, expires__gt=timezone.now(), used__lt=F("limit")
            ).aexists():
                return

    try:
        await send({"type": "websocket.accept"})
        tasks = [asyncio.create_task(f()) for f in (upload, download, watchdog)]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        writer.close()
        with suppress(OSError, RuntimeError):
            await send({"type": "websocket.close", "code": 1000})
            await writer.wait_closed()
