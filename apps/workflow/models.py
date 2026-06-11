from django.db import models
from apps.users.models import User


class WorkflowTemplate(models.Model):
    """流程模板"""
    name = models.CharField('流程名称', max_length=200)
    description = models.TextField('流程描述', blank=True, default='')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_templates'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '流程模板'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class WorkflowStep(models.Model):
    """流程步骤模板"""
    template = models.ForeignKey(
        WorkflowTemplate, on_delete=models.CASCADE, related_name='steps'
    )
    name = models.CharField('步骤名称', max_length=200)
    order = models.IntegerField('步骤顺序', default=0)
    description = models.TextField('步骤说明', blank=True, default='')

    class Meta:
        verbose_name = '流程步骤'
        ordering = ['order']

    def __str__(self):
        return f'{self.template.name} - {self.name}'


class WorkflowInstance(models.Model):
    """流程实例（学生发起的流程）"""
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_REJECTED = 'rejected'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_PENDING, '待处理'),
        (STATUS_IN_PROGRESS, '进行中'),
        (STATUS_COMPLETED, '已完成'),
        (STATUS_REJECTED, '已驳回'),
        (STATUS_EXPIRED, '已过期'),
    ]

    template = models.ForeignKey(
        WorkflowTemplate, on_delete=models.CASCADE, related_name='instances'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='workflow_instances'
    )
    title = models.CharField('流程标题', max_length=200)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    current_step = models.ForeignKey(
        WorkflowStep, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='current_instances'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    deadline = models.DateTimeField('截止时间', null=True, blank=True)
    notes = models.TextField('备注', blank=True, default='')

    class Meta:
        verbose_name = '流程实例'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} - {self.user.real_name or self.user.username}'

    @property
    def is_expired(self):
        """判断流程是否已过期（截止时间已过且未完成/未驳回）"""
        from django.utils import timezone
        if not self.deadline:
            return False
        if self.status in (self.STATUS_COMPLETED, self.STATUS_REJECTED):
            return False
        return self.deadline < timezone.now()

    @property
    def effective_status(self):
        """返回有效状态：如果已过期则返回过期状态，否则返回实际状态"""
        if self.is_expired:
            return self.STATUS_EXPIRED
        return self.status

    @property
    def effective_status_display(self):
        """返回有效状态的中文显示"""
        status_map = dict(self.STATUS_CHOICES)
        return status_map.get(self.effective_status, '未知')


class WorkflowStepRecord(models.Model):
    """流程步骤执行记录"""
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, '待处理'),
        (STATUS_APPROVED, '已通过'),
        (STATUS_REJECTED, '已驳回'),
    ]

    instance = models.ForeignKey(
        WorkflowInstance, on_delete=models.CASCADE, related_name='step_records'
    )
    step = models.ForeignKey(
        WorkflowStep, on_delete=models.CASCADE, related_name='records'
    )
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_steps'
    )
    reviewed_at = models.DateTimeField('审批时间', null=True, blank=True)
    comment = models.TextField('审批意见', blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '步骤记录'
        ordering = ['step__order']
