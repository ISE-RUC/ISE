from django.db import models
from apps.users.models import User


class CertificateRequest(models.Model):
    """
    证明开具申请，支持分级审批流：
    学生提交 → 班主任初审 → 团委老师终审
    """
    STATUS_PENDING = 'pending'
    STATUS_FIRST_REVIEW = 'first_review'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, '待初审'),
        (STATUS_FIRST_REVIEW, '待终审'),
        (STATUS_APPROVED, '已通过'),
        (STATUS_REJECTED, '已驳回'),
    ]

    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cert_requests')
    cert_type = models.CharField('证明类型', max_length=100)
    purpose = models.TextField('用途说明')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    first_reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='first_reviews'
    )
    final_reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='final_reviews'
    )
    generated_pdf = models.FileField('生成的PDF', upload_to='certificates/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # 支持 1-2 天内撤回重批
    reviewed_at = models.DateTimeField('审批时间', null=True, blank=True)

    class Meta:
        verbose_name = '证明申请'
        ordering = ['-created_at']
