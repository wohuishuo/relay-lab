from django.contrib import admin
from django.conf import settings
from django.utils.html import format_html
from .models import Pass, Plan

admin.site.site_header = "RelayLab 管理"
admin.site.site_title = "RelayLab"
admin.site.index_title = "访客与权限"


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "hours", "gb", "price", "offered")


@admin.register(Pass)
class PassAdmin(admin.ModelAdmin):
    list_display = ("__str__", "title", "display_status", "created", "expires", "used", "limit")
    list_filter = ("status",)
    readonly_fields = (
        "id",
        "owner",
        "title",
        "hours",
        "price",
        "status",
        "created",
        "expires",
        "used",
        "uploaded",
        "limit",
        "private_link",
    )
    actions = ("approve", "revoke")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="有效订阅（私密）")
    def private_link(self, obj):
        if not obj.available:
            return "当前不可用"
        url = settings.BASE + "/s/" + obj.token("subscription")
        return format_html('<input readonly size="50" value="{}">', url)

    @admin.action(description="按申请时套餐批准", permissions=["change"])
    def approve(self, request, rows):
        self.message_user(request, f"已批准 {Pass.approve(rows)} 个新申请。")

    @admin.action(description="停用访问和已有连接", permissions=["change"])
    def revoke(self, request, rows):
        n = rows.exclude(status=Pass.Status.REVOKED).update(status=Pass.Status.REVOKED)
        self.message_user(request, f"已停用 {n} 个访客凭据。")
