import http.client
import socket
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.urls import reverse
from .models import Pass, Plan
from . import maintenance
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods


@staff_member_required
@never_cache
@require_http_methods(["GET", "POST"])
def owner(request):
    result = None
    private_admin = (
        settings.LOCAL
        and request.user.is_superuser
        and request.META.get("REMOTE_ADDR") in ("127.0.0.1", "::1")
        and bool(settings.CONFIG.get("maintenance"))
    )
    action = request.POST.get("action")
    if request.method == "POST" and action in maintenance.ACTIONS and private_admin:
        if action != "status" and request.POST.get("confirm") != "yes":
            result = "请先勾选确认框。"
        else:
            row = maintenance.command(action)
            messages = {
                "current": "已经是仓库验证过的镜像，本次无需更新。",
                "busy": "已有维护任务正在运行。",
                "unreachable": "管理通道无法连接。",
                "no_shell": "控制台没有可用的管理会话。",
                "needs_staging": "服务器尚无已验收并带回滚的更新包。",
                "identity_mismatch": "主机身份校验失败。",
                "restart_scheduled": "已提交内核重启。稍后点“读取服务器状态”核对启动时间和健康状态。",
                "update_scheduled": "已提交已准备好的更新。稍后重新读取状态。",
                "preflight_failed": "重启前的健康或镜像校验未通过。",
            }
            if row.get("result") == "online":
                result = "管理通道已连接。核心健康：{}；匹配固定镜像：{}；启动于 {}。".format(
                    "是" if row["healthy"] else "否", "是" if row["pinned"] else "否", row["started"]
                )
            else:
                result = messages.get(row.get("result"), "尚未收到执行结果。请先读取状态，再决定是否重试。")
    if request.method == "POST" and request.POST.get("action") == "issue":
        if not request.user.has_perm("portal.change_pass"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        plan = get_object_or_404(Plan, pk=request.POST.get("plan"), offered=True)
        # A repeated form submission returns the same issued pass.
        key = request.session.pop("issue_key", None)
        if key and request.POST.get("issue_key") == key:
            with transaction.atomic():
                grant, _ = Pass.objects.get_or_create(pk=uuid.UUID(key), defaults=plan.terms())
                Pass.approve(Pass.objects.filter(pk=grant.pk))
            return redirect(reverse("admin:portal_pass_change", args=[grant.pk]))
        return redirect("/owner/")
    private_file = settings.CONFIG.get("owner_subscription_file")
    if request.method == "POST" and request.POST.get("action") == "probe" and private_file:
        # Fixed owner-configured origin. Refuse redirects to keep the bearer path local to its issuer.
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
                import json

                data = reply.read(512 * 1024)
                ok = reply.status == 200 and bool(json.loads(data).get("proxies"))
            finally:
                conn.close()
            result = "日本订阅在线，HTTPS 校验通过，订阅含节点。" if ok else "未通过订阅内容校验。"
        except (OSError, ValueError, http.client.HTTPException):
            result = "本次检查失败，节点状态待确认。"
    try:
        with socket.create_connection(("127.0.0.1", settings.CONFIG["core_port"]), timeout=1):
            guest_status = "访客内核正在监听。本项只检查本机端口。"
    except OSError:
        guest_status = "访客内核当前不可达。"
    issue_key = request.session.setdefault("issue_key", uuid.uuid4().hex)
    return render(
        request,
        "portal/owner.html",
        {
            "result": result,
            "probe": bool(private_file),
            "issue_key": issue_key,
            "private_admin": private_admin,
            "plans": Plan.objects.filter(offered=True).order_by("price", "pk"),
            "console": settings.CONFIG.get("owner_console_url"),
            "guest_status": guest_status,
        },
    )
