#!/usr/bin/env python
"""修复流程中异常截止时间的数据"""
import os
import sys
import django

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from apps.workflow.models import WorkflowInstance
from django.utils import timezone

def fix_deadline():
    """清理异常的截止时间"""
    # 查找所有截止时间在2000年之前或2100年之后的流程
    instances = WorkflowInstance.objects.all()
    fixed = 0
    
    for instance in instances:
        if instance.deadline:
            if instance.deadline.year < 2000 or instance.deadline.year > 2100:
                print(f"修复流程 #{instance.id}: {instance.title}")
                print(f"  原截止时间: {instance.deadline}")
                instance.deadline = None
                instance.save()
                fixed += 1
                print(f"  已清除异常截止时间")
    
    print(f"\n共修复 {fixed} 条记录")

if __name__ == '__main__':
    fix_deadline()
