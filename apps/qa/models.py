from django.db import models
from apps.users.models import User


class PolicyDocument(models.Model):
    """政策文件库，支持 PDF/Word，单文件 ≤30MB。"""
    title = models.CharField('标题', max_length=200)
    file = models.FileField('文件', upload_to='qa/policies/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '政策文件'


class FAQEntry(models.Model):
    """标准问答条目，优先匹配以避免 AI 幻觉。"""
    question = models.CharField('问题', max_length=500)
    answer = models.TextField('标准回答')
    related_doc = models.ForeignKey(PolicyDocument, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '标准问答'


class FormTemplate(models.Model):
    """可下载的表单模板（请假条、证明模板等）。"""
    name = models.CharField('模板名称', max_length=200)
    file = models.FileField('模板文件', upload_to='qa/templates/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '表单模板'
