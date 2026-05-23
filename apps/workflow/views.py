from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.workflow.models import (
    WorkflowTemplate, WorkflowStep, WorkflowInstance, WorkflowStepRecord
)
from apps.users.models import User


class SelectView(TemplateView):
    """选择端页面"""
    template_name = 'workflow/select.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_admin'] = user.is_authenticated and user.role in (User.ROLE_ADMIN, User.ROLE_LEADER)
        return context


class StudentView(TemplateView):
    """学生端 - 查看自己的流程"""
    template_name = 'workflow/student.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        instances = []
        templates = WorkflowTemplate.objects.all()
        if user.is_authenticated:
            instances = WorkflowInstance.objects.filter(user=user).select_related(
                'template', 'current_step'
            ).order_by('-created_at')
        context.update({
            'student': user if user.is_authenticated else None,
            'instances': instances,
            'templates': templates,
        })
        return context


class StudentDetailView(TemplateView):
    """学生端 - 流程详情"""
    template_name = 'workflow/student_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        pk = kwargs.get('pk')

        instance = get_object_or_404(
            WorkflowInstance.objects.select_related('template', 'current_step', 'user'),
            pk=pk
        )

        # 权限检查：只能查看自己的流程
        if user.is_authenticated and instance.user != user:
            messages.error(context.get('request', None), '您没有权限查看此流程。')
            return context

        step_records = WorkflowStepRecord.objects.filter(
            instance=instance
        ).select_related('step', 'reviewer').order_by('step__order')

        # 计算倒计时
        countdown = None
        if instance.deadline:
            delta = instance.deadline - timezone.now()
            if delta.days > 0:
                countdown = f'{delta.days} 天'
            elif delta.seconds > 3600:
                countdown = f'{delta.seconds // 3600} 小时'
            elif delta.seconds > 60:
                countdown = f'{delta.seconds // 60} 分钟'
            else:
                countdown = '已到期'

        context.update({
            'instance': instance,
            'step_records': step_records,
            'countdown': countdown,
        })
        return context


class AdminView(TemplateView):
    """管理端 - 管理流程"""
    template_name = 'workflow/admin.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # 权限检查
        if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
            context['no_permission'] = True
            context['templates'] = []
            context['instances'] = []
            return context

        templates = WorkflowTemplate.objects.all().order_by('-created_at')
        instances = WorkflowInstance.objects.select_related(
            'template', 'user', 'current_step'
        ).order_by('-created_at')

        context.update({
            'templates': templates,
            'instances': instances,
        })
        return context


class AdminDetailView(TemplateView):
    """管理端 - 流程详情"""
    template_name = 'workflow/admin_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        pk = kwargs.get('pk')

        # 权限检查
        if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
            context['no_permission'] = True
            return context

        instance = get_object_or_404(
            WorkflowInstance.objects.select_related('template', 'current_step', 'user'),
            pk=pk
        )

        step_records = WorkflowStepRecord.objects.filter(
            instance=instance
        ).select_related('step', 'reviewer').order_by('step__order')

        # 计算倒计时
        countdown = None
        if instance.deadline:
            delta = instance.deadline - timezone.now()
            if delta.days > 0:
                countdown = f'{delta.days} 天'
            elif delta.seconds > 3600:
                countdown = f'{delta.seconds // 3600} 小时'
            elif delta.seconds > 60:
                countdown = f'{delta.seconds // 60} 分钟'
            else:
                countdown = '已到期'

        context.update({
            'instance': instance,
            'step_records': step_records,
            'countdown': countdown,
        })
        return context


class CreateTemplateView(View):
    """创建流程模板"""
    def post(self, request):
        user = request.user
        if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
            messages.error(request, '您没有权限执行此操作。')
            return redirect('workflow:select')

        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        steps_text = request.POST.get('steps', '').strip()

        if not name:
            messages.error(request, '请输入流程名称。')
            return redirect('workflow:admin')

        template = WorkflowTemplate.objects.create(
            name=name,
            description=description,
            created_by=user
        )

        # 解析步骤（每行一个步骤）
        if steps_text:
            for i, step_name in enumerate(steps_text.split('\n'), 1):
                step_name = step_name.strip()
                if step_name:
                    WorkflowStep.objects.create(
                        template=template,
                        name=step_name,
                        order=i
                    )

        messages.success(request, f'已创建流程模板：{name}')
        return redirect('workflow:admin')


class CreateInstanceView(View):
    """创建流程实例（学生发起流程）"""
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            messages.error(request, '请先登录。')
            return redirect('workflow:select')

        template_id = request.POST.get('template_id')
        title = request.POST.get('title', '').strip()
        deadline = request.POST.get('deadline', '').strip()

        if not template_id:
            messages.error(request, '请选择流程模板。')
            return redirect('workflow:student')
        if not title:
            messages.error(request, '请输入流程标题。')
            return redirect('workflow:student')

        template = get_object_or_404(WorkflowTemplate, pk=template_id)

        # 创建流程实例
        instance = WorkflowInstance.objects.create(
            template=template,
            user=user,
            title=title,
            status=WorkflowInstance.STATUS_IN_PROGRESS
        )

        # 设置截止时间
        if deadline:
            try:
                instance.deadline = deadline
                instance.save()
            except Exception:
                pass

        # 获取第一步
        first_step = template.steps.order_by('order').first()
        if first_step:
            instance.current_step = first_step
            instance.save()

            # 创建所有步骤记录
            for step in template.steps.order_by('order'):
                WorkflowStepRecord.objects.create(
                    instance=instance,
                    step=step,
                    status='pending' if step != first_step else 'pending'
                )

        messages.success(request, f'已发起流程：{title}')
        return redirect('workflow:student_detail', pk=instance.pk)


class ReviewStepView(View):
    """审批流程步骤"""
    def post(self, request, pk):
        user = request.user
        if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
            messages.error(request, '您没有权限执行此操作。')
            return redirect('workflow:select')

        instance = get_object_or_404(WorkflowInstance, pk=pk)
        action = request.POST.get('action')
        comment = request.POST.get('comment', '').strip()

        # 获取当前步骤记录
        current_record = WorkflowStepRecord.objects.filter(
            instance=instance,
            step=instance.current_step
        ).first()

        if not current_record:
            messages.error(request, '当前没有待处理的步骤。')
            return redirect('workflow:admin_detail', pk=pk)

        # 更新步骤状态
        current_record.reviewer = user
        current_record.reviewed_at = timezone.now()
        current_record.comment = comment

        if action == 'approve':
            current_record.status = WorkflowStepRecord.STATUS_APPROVED

            # 检查是否有下一步
            next_step = WorkflowStep.objects.filter(
                template=instance.template,
                order__gt=instance.current_step.order
            ).order_by('order').first()

            if next_step:
                instance.current_step = next_step
                instance.save()
                messages.success(request, f'已通过当前步骤，进入下一步：{next_step.name}')
            else:
                # 所有步骤完成
                instance.status = WorkflowInstance.STATUS_COMPLETED
                instance.save()
                messages.success(request, '流程已完成！')
        elif action == 'reject':
            current_record.status = WorkflowStepRecord.STATUS_REJECTED
            instance.status = WorkflowInstance.STATUS_REJECTED
            instance.save()
            messages.success(request, '已驳回该流程。')

        current_record.save()
        return redirect('workflow:admin_detail', pk=pk)


class DeleteTemplateView(View):
    """删除流程模板"""
    def post(self, request, pk):
        user = request.user
        if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
            messages.error(request, '您没有权限执行此操作。')
            return redirect('workflow:select')

        template = get_object_or_404(WorkflowTemplate, pk=pk)
        template_name = template.name
        template.delete()
        messages.success(request, f'已删除流程模板：{template_name}')
        return redirect('workflow:admin')


class DeleteInstanceView(View):
    """删除流程实例"""
    def post(self, request, pk):
        user = request.user
        if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
            messages.error(request, '您没有权限执行此操作。')
            return redirect('workflow:select')

        instance = get_object_or_404(WorkflowInstance, pk=pk)
        instance_title = instance.title
        instance.delete()
        messages.success(request, f'已删除流程：{instance_title}')
        return redirect('workflow:admin')
