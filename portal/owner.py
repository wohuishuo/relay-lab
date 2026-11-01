import http.client
import json
import socket
import ssl
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from . import guest_admin, maintenance
from .models import Pass, Plan


def subscription_check(private_file):
    # Only the configured origin receives the bearer path. Never follow redirects.
    try:
        url = urlsplit(Path(private_file).read_text(encoding="utf-8").strip())
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError
        proxy = settings.CONFIG.get("owner_proxy_port")
        if proxy:
            conn = http.client.HTTPSConnection("127.0.0.1", int(proxy), timeout=8)
            conn.set_tunnel(url.hostname, url.port or 443)
        else:
            conn = http.client.HTTPSConnection(url.hostname, url.port or 443, timeout=8)
        try:
            conn.request("GET", url.path + ("?" + url.query if url.query else ""))
            reply = conn.getresponse()
            if reply.status != 200:
                return "error", "订阅下载失败", f"服务器返回 HTTP {reply.status}。"
            data = json.loads(reply.read(512 * 1024))
        finally:
            conn.close()
        nodes = data.get("proxies") if isinstance(data, dict) else None
        if not isinstance(nodes, list) or not nodes:
            return "error", "订阅内容有误", "下载成功，但配置中没有节点列表。"
        return "ok", "日本订阅在线", f"HTTPS 证书校验通过，本次下载的订阅包含 {len(nodes)} 个节点。"
    except (OSError, ValueError, http.client.HTTPException):
        return "error", "订阅检查失败", "未能通过当前网络读取并验证订阅。可重试，或单独读取服务器状态。"


def guest_check():
    try:
        tls = ssl.create_default_context(cafile=str(settings.STATE / "core-state" / "loopback.crt"))
        with socket.create_connection(("127.0.0.1", settings.CONFIG["core_port"]), timeout=2) as conn:
            with tls.wrap_socket(conn, server_hostname="relay-guest.internal"):
                pass
        return "ok", "本机访客入口可连接", "已与访客内核完成 TLS 握手并校验证书。此项只检查本机入口。"
    except ssl.SSLError:
        return "error", "访客 TLS 检查失败", "请检查访客证书和内核的 TLS 配置。"
    except OSError:
        return "error", "本机访客入口不可达", "请检查本机访客服务及其证书文件。"


def maintenance_result(action):
    row = maintenance.command(action)
    if row.get("result") == "online":
        started = timezone.localtime(datetime.fromisoformat(row["started"])).strftime("%Y-%m-%d %H:%M:%S")
        return (
            "ok" if row["healthy"] and row["pinned"] else "warning",
            "日本核心健康" if row["healthy"] else "已连接，核心健康检查未通过",
            f"可用内存 {row['memory_available_mib']} MiB · 容器重启计数 {row['restarts']} · "
            f"镜像{'匹配' if row['pinned'] else '未匹配'}固定版本 · 启动于 {started}（北京时间）",
        )
    outcomes = {
        "current": ("ok", "已是验证版本", "当前镜像与仓库固定版本一致，无需更新。"),
        "busy": ("warning", "维护通道正在使用", "请等当前操作结束后重试。"),
        "unreachable": ("error", "管理通道无法连接", "可用订阅检查单独确认节点是否仍可使用。"),
        "no_shell": ("error", "控制台没有可用的管理会话", "可经 Linode 控制台检查登录状态。"),
        "needs_staging": ("warning", "暂无可用更新", "主机尚未准备经过验收、可回滚的更新包。"),
        "identity_mismatch": ("error", "主机身份校验失败", "操作已停止。"),
        "restart_scheduled": ("warning", "已提交核心重启", "稍后读取服务器状态，核对启动时间和健康状态。"),
        "update_scheduled": ("warning", "已提交更新", "稍后重新读取状态确认执行结果。"),
        "preflight_failed": ("error", "重启前检查未通过", "请先读取核心健康状态和镜像版本。"),
    }
    return outcomes.get(row.get("result"), ("warning", "没有收到确定结果", "请先读取服务器状态再重试。"))


def issue(request):
    if not request.user.has_perm("portal.change_pass"):
        raise PermissionDenied
    plan = get_object_or_404(Plan, pk=request.POST.get("plan"), offered=True)
    key = request.session.pop("issue_key", None)
    if key and request.POST.get("issue_key") == key:
        with transaction.atomic():
            grant, _ = Pass.objects.get_or_create(pk=uuid.UUID(key), defaults=plan.terms())
            Pass.approve(Pass.objects.filter(pk=grant.pk))
        messages.success(request, "通行证已签发。可在下方复制订阅链接。")
        return redirect(reverse("admin:portal_pass_change", args=[grant.pk]))
    return redirect("owner")


@staff_member_required
@never_cache
@require_http_methods(["GET", "POST"])
def owner(request):
    private_admin = (
        settings.LOCAL and request.user.is_superuser
        and request.META.get("REMOTE_ADDR") in ("127.0.0.1", "::1") and bool(settings.CONFIG.get("maintenance"))
    )
    private_file = settings.CONFIG.get("owner_subscription_file")
    public_guest = settings.CONFIG.get("public_guest") if private_admin else None
    feedback = {}
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "issue":
            return issue(request)
        start = time.monotonic()
        if action == "public_admin":
            if not public_guest:
                raise PermissionDenied
            if guest_admin.connect():
                return redirect("http://localhost:18769/owner/")
            result = ("error", "未能打开私有访客管理通道", "请确认个人节点可用后重试。")
        elif action in maintenance.ACTIONS:
            if not private_admin:
                raise PermissionDenied
            if action != "status" and request.POST.get("confirm") != "yes":
                result = ("warning", "尚未执行", "请先勾选确认框。")
            else:
                result = maintenance_result(action)
        elif action == "probe" and private_file:
            result = subscription_check(private_file)
        elif action == "check":
            result = guest_check()
        else:
            return HttpResponseBadRequest("未知或未启用的操作")
        panel = "maintenance" if action in ("restart", "update") else action
        state, summary, detail = result
        outcome = {"state": state, "summary": summary, "detail": detail,
                   "stamp": timezone.localtime().strftime("%H:%M:%S 北京时间") + f" · 耗时 {time.monotonic()-start:.1f} 秒"}
        if request.headers.get("Accept") == "application/json":
            return JsonResponse(outcome)
        if panel == "maintenance":
            request.session["maintenance_notice"] = outcome
            return redirect(reverse("owner") + "#maintenance")
        feedback[panel] = outcome
    if request.method == "GET" and "maintenance_notice" in request.session:
        feedback["maintenance"] = request.session.pop("maintenance_notice")
    return render(request, "portal/owner.html", {
        **admin.site.each_context(request), "title": "节点运维", "feedback": feedback,
        "probe": bool(private_file), "private_admin": private_admin, "local": settings.LOCAL,
        "issue_key": request.session.setdefault("issue_key", uuid.uuid4().hex),
        "plans": Plan.objects.filter(offered=True).order_by("price", "pk"),
        "console": settings.CONFIG.get("owner_console_url"), "public_guest": public_guest,
    })
