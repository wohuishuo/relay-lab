from django.contrib import admin
from django.conf import settings
from django.utils.html import format_html
from .models import Inquiry, Pass, Plan

admin.site.site_header = "RelayLab 管理"
admin.site.site_title = "RelayLab"
admin.site.index_title = "访客与权限"


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ("__str__", "sender", "created", "answered")
    readonly_fields = ("sender", "question", "created")
    fields = ("sender", "created", "question", "answer")

    @admin.display(boolean=True, description="已回复")
    def answered(self, obj):
        return bool(obj.answer)

    def has_add_permission(self, request):
        return False


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "hours", "gb", "price", "offered")


@admin.register(Pass)
class PassAdmin(admin.ModelAdmin):
    list_display = ("__str__", "title", "display_status", "balance", "valid_for", "expires")
    list_filter = ("status",)
    readonly_fields = (
        "id",
        "owner",
        "title",
        "hours",
        "price",
        "status",
        "balance",
        "valid_for",
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

    @admin.display(description="剩余流量")
    def balance(self, obj):
        return obj.remaining_data

    @admin.display(description="距离到期")
    def valid_for(self, obj):
        return obj.remaining_time

    @admin.display(description="有效订阅（私密）")
    def private_link(self, obj):
        if not obj.available:
            return "当前不可用"
        url = settings.BASE + "/s/" + obj.token("subscription")
        note = "仅本机可用。" if settings.LOCAL else ""
        return format_html('<input readonly size="46" aria-label="订阅链接" value="{}"><p>{}在 Clash 中以订阅链接导入，刷新后可查看余额和到期时间。</p>', url, note)

    @admin.action(description="按申请时套餐批准", permissions=["change"])
    def approve(self, request, rows):
        self.message_user(request, f"已批准 {Pass.approve(rows)} 个新申请。")

    @admin.action(description="停用访问和已有连接", permissions=["change"])
    def revoke(self, request, rows):
        n = rows.exclude(status=Pass.Status.REVOKED).update(status=Pass.Status.REVOKED)
        self.message_user(request, f"已停用 {n} 个访客凭据。")
