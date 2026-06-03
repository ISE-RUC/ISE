from django.db import models
from django.utils import timezone

from apps.users.models import User


class CertificateRequest(models.Model):
    """证明申请单。"""

    STATUS_DRAFT = "draft"
    STATUS_MATERIAL_PENDING = "material_pending"
    STATUS_MATERIAL_REJECTED = "material_rejected"
    STATUS_PENDING_REVIEW = "pending_review"
    STATUS_REJECTED = "rejected"
    STATUS_APPROVED_OBSERVING = "approved_observing"
    STATUS_REVOKED = "revoked"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "待提交"),
        (STATUS_MATERIAL_PENDING, "待材料校验"),
        (STATUS_MATERIAL_REJECTED, "待补充材料"),
        (STATUS_PENDING_REVIEW, "待管理员处理"),
        (STATUS_REJECTED, "审批驳回"),
        (STATUS_APPROVED_OBSERVING, "24小时观察期"),
        (STATUS_REVOKED, "已撤回作废"),
        (STATUS_COMPLETED, "已办结"),
    ]

    applicant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="certificate_requests",
        null=True,
        blank=True,
    )
    reference_no = models.CharField("申请单号", max_length=40, unique=True)
    cert_type = models.CharField("证明类型", max_length=100)
    purpose = models.TextField("用途说明", blank=True)
    attachment_note = models.TextField("补充材料说明", blank=True)
    status = models.CharField("状态", max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    rejection_reason = models.TextField("驳回意见", blank=True)
    generated_pdf = models.FileField("生成文件", upload_to="certificates/", null=True, blank=True)
    is_pdf_void = models.BooleanField("PDF是否作废", default=False)
    submitted_at = models.DateTimeField("提交时间", null=True, blank=True)
    approved_at = models.DateTimeField("审批通过时间", null=True, blank=True)
    revoke_deadline = models.DateTimeField("撤回截止时间", null=True, blank=True)
    revoked_at = models.DateTimeField("撤回时间", null=True, blank=True)
    completed_at = models.DateTimeField("办结时间", null=True, blank=True)
    last_operator = models.CharField("最近操作人", max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "证明申请"
        verbose_name_plural = "证明申请"
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return f"{self.reference_no} - {self.cert_type}"

    @property
    def in_observing_window(self):
        return (
            self.status == self.STATUS_APPROVED_OBSERVING
            and self.revoke_deadline is not None
            and self.revoke_deadline > timezone.now()
        )


class CertificateMaterial(models.Model):
    """申请相关材料记录。"""

    request = models.ForeignKey(
        CertificateRequest,
        on_delete=models.CASCADE,
        related_name="materials",
    )
    name = models.CharField("材料名称", max_length=100)
    detail = models.TextField("材料说明", blank=True)
    is_required = models.BooleanField("是否必填", default=True)
    is_valid = models.BooleanField("是否通过校验", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "证明材料"
        verbose_name_plural = "证明材料"
        ordering = ["id"]


class CertificateLog(models.Model):
    """证明流程日志。"""

    request = models.ForeignKey(
        CertificateRequest,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    action = models.CharField("操作", max_length=100)
    detail = models.TextField("详情", blank=True)
    operator = models.CharField("操作人", max_length=100, blank=True)
    created_at = models.DateTimeField("时间", auto_now_add=True)

    class Meta:
        verbose_name = "证明流程日志"
        verbose_name_plural = "证明流程日志"
        ordering = ["created_at", "id"]
