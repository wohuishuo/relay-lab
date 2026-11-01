import uuid
from datetime import timedelta
from django.conf import settings
from django.core import signing
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

TRIAL_BYTES = 10_000_000_000
TRIAL_HOURS = 72


class Plan(models.Model):
    name = models.CharField("套餐名称", max_length=64, unique=True)
    hours = models.PositiveIntegerField(
        "有效小时", default=72, validators=[MinValueValidator(1), MaxValueValidator(8760)]
    )
    gb = models.PositiveIntegerField(
        "总流量 GB", default=10, validators=[MinValueValidator(1), MaxValueValidator(10000)]
    )
    price = models.DecimalField(
        "展示价格（人民币元）", max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    offered = models.BooleanField("接受新申请", default=True)

    class Meta:
        verbose_name = verbose_name_plural = "套餐"

    def __str__(self):
        return self.name

    def terms(self):
        return {
            "title": self.name,
            "hours": self.hours,
            "limit": self.gb * 1_000_000_000,
            "price": self.price,
        }


class Pass(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "等待审批"
        ACTIVE = "active", "已批准"
        REVOKED = "revoked", "已停用"
        EXHAUSTED = "exhausted", "额度用尽"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, verbose_name="申请人"
    )
    title = models.CharField("套餐", max_length=64, default="三天体验")
    hours = models.PositiveIntegerField("有效小时", default=TRIAL_HOURS)
    price = models.DecimalField("申请时价格（元）", max_digits=8, decimal_places=2, default=0)
    status = models.CharField("审批状态", max_length=12, choices=Status, default=Status.PENDING)
    created = models.DateTimeField("申请时间", auto_now_add=True)
    expires = models.DateTimeField("有效期至", null=True)
    used = models.PositiveBigIntegerField("已计费字节", default=0)
    uploaded = models.PositiveBigIntegerField("上行字节", default=0)
    limit = models.PositiveBigIntegerField("可用总字节", default=TRIAL_BYTES)

    class Meta:
        verbose_name = verbose_name_plural = "访客申请与额度"

    def __str__(self):
        return str(self.owner) if self.owner_id else f"临时通行证 {self.id.hex[:8]}"

    @property
    def available(self):
        return (
            self.status == self.Status.ACTIVE
            and self.expires
            and self.expires > timezone.now()
            and self.used < self.limit
        )

    @property
    def display_status(self):
        if self.status == self.Status.ACTIVE and self.used >= self.limit:
            return "额度用尽"
        if self.status == self.Status.ACTIVE and self.expires and self.expires <= timezone.now():
            return "已到期"
        return self.get_status_display()

    def token(self, purpose):
        return signing.Signer(salt="relay.portal." + purpose).sign(self.id.hex)

    @classmethod
    def from_token(cls, token, purpose):
        try:
            key = uuid.UUID(hex=signing.Signer(salt="relay.portal." + purpose).unsign(token))
        except (ValueError, signing.BadSignature):
            return None
        return cls.objects.filter(
            pk=key, status=cls.Status.ACTIVE, expires__gt=timezone.now(), used__lt=F("limit")
        ).first()

    @classmethod
    def approve(cls, rows):
        with transaction.atomic():
            total = 0
            now = timezone.now()
            for row in rows.filter(status=cls.Status.PENDING).only("id", "hours"):
                row.status = cls.Status.ACTIVE
                row.expires = now + timedelta(hours=row.hours)
                row.save(update_fields=["status", "expires"])
                total += 1
            return total

    @classmethod
    def charge(cls, key, size, *, upload=False):
        # Both directions and every device share one durable budget. Reserve before forwarding.
        with transaction.atomic():
            rows = cls.objects.filter(pk=key, status=cls.Status.ACTIVE, expires__gt=timezone.now())
            increments = {"used": F("used") + size}
            if upload:
                increments["uploaded"] = F("uploaded") + size
            if rows.filter(used__lte=F("limit") - size).update(**increments):
                return True
            # Refuse the entire last frame. Never charge data we rejected.
            rows.update(status=cls.Status.EXHAUSTED)
        return False
