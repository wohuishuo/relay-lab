import json
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods
from .models import Pass, Plan
from .owner import owner


@never_cache
def home(request):
    current = Pass.objects.filter(owner=request.user).first() if request.user.is_authenticated else None
    link = settings.BASE + "/s/" + current.token("subscription") if current and current.available else None
    return render(
        request,
        "portal/home.html",
        {
            "grant": current,
            "link": link,
            "local": settings.LOCAL,
            "plans": Plan.objects.filter(offered=True).order_by("price", "pk"),
        },
    )


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("/")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("/")
    return render(request, "portal/form.html", {"form": form, "title": "创建访客账号"})


@require_POST
@login_required
def apply(request):
    plan = get_object_or_404(Plan, pk=request.POST.get("plan"), offered=True)
    Pass.objects.get_or_create(owner=request.user, defaults=plan.terms())
    return redirect("/")


@never_cache
def subscribe(request, token):
    grant = Pass.from_token(token, "subscription")
    if not grant:
        raise Http404
    origin = settings.ORIGIN
    proxy = {
        "name": "Guest",
        "type": "vless",
        "server": origin.hostname,
        "port": origin.port or 443,
        "uuid": settings.CONFIG["guest_uuid"],
        "network": "ws",
        "tls": origin.scheme == "https",
        "servername": origin.hostname,
        "udp": False,
        "ws-opts": {
            "path": "/connect",
            "headers": {"Host": origin.netloc, "Authorization": "Bearer " + grant.token("wire")},
        },
    }
    config = {
        "mode": "rule",
        "proxies": [proxy],
        "proxy-groups": [{"name": "Guest access", "type": "select", "proxies": ["Guest"]}],
        "rules": ["MATCH,Guest access"],
    }
    response = HttpResponse(json.dumps(config), content_type="application/yaml")
    response["Subscription-Userinfo"] = (
        f"upload={grant.uploaded}; download={grant.used - grant.uploaded}; total={grant.limit}; expire={int(grant.expires.timestamp())}"
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    return response


urlpatterns = [
    path("", home),
    path("owner/", owner),
    path("register/", register),
    path("apply/", apply),
    path("s/<str:token>", subscribe),
    path("login/", LoginView.as_view(template_name="portal/form.html", extra_context={"title": "登录"})),
    path("logout/", LogoutView.as_view()),
    path("admin/", admin.site.urls),
]
