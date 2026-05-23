from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Extended user model for the campus platform.

    Role levels:
    1 = leader
    2 = admin teacher
    3 = cadre
    4 = student
    """

    ROLE_LEADER = 1
    ROLE_ADMIN = 2
    ROLE_CADRE = 3
    ROLE_STUDENT = 4

    ROLE_CHOICES = [
        (ROLE_LEADER, "学院领导"),
        (ROLE_ADMIN, "管理老师"),
        (ROLE_CADRE, "班团骨干"),
        (ROLE_STUDENT, "普通学生"),
    ]

    student_id = models.CharField("学号", max_length=20, unique=True, null=True, blank=True)
    employee_id = models.CharField("教职工号", max_length=20, unique=True, null=True, blank=True)
    role = models.IntegerField("角色", choices=ROLE_CHOICES, default=ROLE_STUDENT)
    real_name = models.CharField("真实姓名", max_length=50, blank=True)
    grade = models.CharField("年级", max_length=10, blank=True)
    major = models.CharField("专业", max_length=100, blank=True)
    email = models.EmailField("邮箱", blank=True)

    # Sensitive fields are still protected in the view layer.
    id_number = models.CharField("身份证号", max_length=18, blank=True)
    hometown = models.CharField("生源地", max_length=100, blank=True)
    suspension_record = models.TextField("休学/延毕记录", blank=True)

    USERNAME_FIELD = "username"

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def get_display_name(self):
        return self.real_name or self.username

    def get_login_account(self):
        if self.role in (self.ROLE_ADMIN, self.ROLE_LEADER):
            return self.employee_id or self.username
        return self.student_id or self.username

    def is_leader(self):
        return self.role == self.ROLE_LEADER

    def is_admin_or_above(self):
        return self.role <= self.ROLE_ADMIN

    def is_cadre_or_above(self):
        return self.role <= self.ROLE_CADRE

    def can_manage_party(self):
        return self.role <= self.ROLE_ADMIN

    def can_publish_notice(self):
        return self.role <= self.ROLE_CADRE

    def can_view_sensitive(self):
        return self.role <= self.ROLE_ADMIN


class AuditLog(models.Model):
    """Simple audit log for write operations."""

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField("操作", max_length=200)
    target_model = models.CharField("对象类型", max_length=100, blank=True)
    target_id = models.CharField("对象ID", max_length=50, blank=True)
    detail = models.TextField("详情", blank=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    created_at = models.DateTimeField("时间", auto_now_add=True)

    class Meta:
        verbose_name = "操作日志"
        ordering = ["-created_at"]
