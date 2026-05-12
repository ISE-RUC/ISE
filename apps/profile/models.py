from django.db import models
from apps.users.models import User


class Honor(models.Model):
    """荣誉记录（国奖、校优等）。"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='honors')
    title = models.CharField('荣誉名称', max_length=200)
    level = models.CharField('级别', max_length=50)  # 国家级/校级/院级
    awarded_at = models.DateField('获奖日期')
    attachment = models.FileField('证明材料', upload_to='profile/honors/', null=True, blank=True)

    class Meta:
        verbose_name = '荣誉记录'
        ordering = ['-awarded_at']


class WorkRecord(models.Model):
    """学生骨干工作量记录，用于期末评优。"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='work_records')
    description = models.CharField('工作描述', max_length=300)
    work_date = models.DateField('工作日期')
    hours = models.DecimalField('工时', max_digits=5, decimal_places=1, default=0)
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='recorded_works'
    )

    class Meta:
        verbose_name = '工作量记录'
        ordering = ['-work_date']
