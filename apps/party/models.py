from django.db import models
from apps.users.models import User


class PartyMemberStatus(models.Model):
    """
    党员发展状态机。
    状态严格线性，不可越级：申请人→积极分子→发展对象→预备党员→正式党员
    """
    STATUS_APPLICANT = 'applicant'
    STATUS_ACTIVIST = 'activist'
    STATUS_CANDIDATE = 'candidate'
    STATUS_PROBATIONARY = 'probationary'
    STATUS_FULL = 'full'
    STATUS_CHOICES = [
        (STATUS_APPLICANT, '入党申请人'),
        (STATUS_ACTIVIST, '积极分子'),
        (STATUS_CANDIDATE, '发展对象'),
        (STATUS_PROBATIONARY, '预备党员'),
        (STATUS_FULL, '正式党员'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='party_status')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_APPLICANT)
    status_since = models.DateField('进入当前状态日期', null=True, blank=True)
    notes = models.TextField('备注', blank=True)

    class Meta:
        verbose_name = '党员发展状态'


class PartyProgressRecord(models.Model):
    """党员发展流程节点记录（思想汇报、培训等）。"""
    member = models.ForeignKey(PartyMemberStatus, on_delete=models.CASCADE, related_name='records')
    node_name = models.CharField('节点名称', max_length=100)
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)
    file = models.FileField('附件', upload_to='party/records/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '流程节点记录'
        ordering = ['created_at']
