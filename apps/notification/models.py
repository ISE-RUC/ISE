from django.db import models
from apps.users.models import User


class Notification(models.Model):
    """通知消息，支持按年级/专业/角色精准推送。"""
    title = models.CharField('标题', max_length=200)
    content = models.TextField('内容')
    publisher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    # 推送目标过滤条件（空=全体）
    target_grade = models.CharField('目标年级', max_length=10, blank=True)
    target_major = models.CharField('目标专业', max_length=100, blank=True)
    target_role = models.IntegerField('目标角色', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '通知'
        ordering = ['-created_at']


class NotificationRead(models.Model):
    """记录用户已读状态。"""
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('notification', 'user')
