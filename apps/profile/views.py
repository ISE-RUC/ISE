from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from ninja import Router, Schema
from typing import Optional

from apps.profile.models import Honor
from apps.users.models import User
from utils.response import error, success

router = Router()

CATEGORY_CHOICES = [
    ('academic', '学术竞赛'),
    ('sports', '文体活动'),
    ('social', '社会实践'),
    ('volunteer', '志愿服务'),
    ('party', '党团活动'),
    ('other', '其他'),
]


def _serialize_honor(honor):
    return {
        'id': honor.id,
        'user_id': honor.user_id,
        'user_name': honor.user.real_name or honor.user.username,
        'student_id': honor.user.student_id or '',
        'title': honor.title,
        'category': honor.category,
        'category_display': honor.get_category_display(),
        'level': honor.level,
        'description': honor.description or '',
        'awarded_at': honor.awarded_at.strftime('%Y-%m-%d') if honor.awarded_at else '',
        'attachment_url': honor.attachment.url if honor.attachment else '',
    }


class SelectView(LoginRequiredMixin, TemplateView):
    """选择端页面"""
    template_name = 'profile/select.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_admin'] = user.is_authenticated and user.role in (User.ROLE_ADMIN, User.ROLE_LEADER)
        return context


class StudentView(LoginRequiredMixin, TemplateView):
    """学生端 - 展示自己的荣誉"""
    template_name = 'profile/student.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        honors = []
        if user.is_authenticated:
            honors = Honor.objects.filter(user=user).order_by('-awarded_at')
        context.update({
            'student': user if user.is_authenticated else None,
            'honors': honors,
        })
        return context


class AdminView(LoginRequiredMixin, TemplateView):
    """管理端 - 录入和管理荣誉"""
    template_name = 'profile/admin.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # 权限检查：只有管理老师和学院领导可以访问
        if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
            context['no_permission'] = True
            context['honors'] = []
            context['category_choices'] = CATEGORY_CHOICES
            return context

        honors = Honor.objects.select_related('user').all().order_by('-awarded_at')
        context.update({
            'honors': honors,
            'category_choices': CATEGORY_CHOICES,
        })
        return context


class AddHonorView(LoginRequiredMixin, View):
    """录入荣誉"""
    def post(self, request):
        user = request.user

        # 权限检查
        if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
            messages.error(request, '您没有权限执行此操作。')
            return redirect('profile:select')

        student_id = request.POST.get('student_id', '').strip()
        title = request.POST.get('title', '').strip()
        category = request.POST.get('category', 'other').strip()
        level = request.POST.get('level', '院级').strip()
        description = request.POST.get('description', '').strip()
        awarded_at = request.POST.get('awarded_at', '').strip()

        if not student_id:
            messages.error(request, '请输入学号。')
            return redirect('profile:admin')
        if not title:
            messages.error(request, '请输入奖项名称。')
            return redirect('profile:admin')

        target_user = User.objects.filter(student_id=student_id).first()
        if not target_user:
            messages.error(request, f'未找到学号为 {student_id} 的学生。')
            return redirect('profile:admin')

        honor_data = {
            'user': target_user,
            'title': title,
            'category': category if category in dict(CATEGORY_CHOICES) else 'other',
            'level': level,
            'description': description,
        }

        if awarded_at:
            try:
                honor_data['awarded_at'] = awarded_at
            except ValueError:
                messages.error(request, '日期格式不正确。')
                return redirect('profile:admin')
        else:
            honor_data['awarded_at'] = timezone.now().date()

        if request.FILES.get('attachment'):
            honor_data['attachment'] = request.FILES['attachment']

        Honor.objects.create(**honor_data)
        messages.success(request, f'已为 {target_user.real_name or target_user.username} 录入荣誉：{title}')
        return redirect('profile:admin')


class DeleteHonorView(LoginRequiredMixin, View):
    """删除荣誉"""
    def post(self, request, pk):
        user = request.user

        # 权限检查
        if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
            messages.error(request, '您没有权限执行此操作。')
            return redirect('profile:select')

        honor = get_object_or_404(Honor, pk=pk)
        honor_title = honor.title
        honor.delete()
        messages.success(request, f'已删除荣誉：{honor_title}')
        return redirect('profile:admin')


@router.get('/overview')
def api_overview(request):
    user = request.user
    honors = []
    if user.is_authenticated:
        honors = Honor.objects.filter(user=user).order_by('-awarded_at')

    return success(data={
        'student': {
            'id': user.id,
            'name': user.real_name or user.username,
            'student_id': user.student_id,
        } if user.is_authenticated else None,
        'honors': [_serialize_honor(h) for h in honors],
        'category_choices': CATEGORY_CHOICES,
    })


@router.get('/all')
def api_all_honors(request):
    user = request.user
    if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
        return error(msg='您没有权限执行此操作。', code=403)

    honors = Honor.objects.select_related('user').all().order_by('-awarded_at')
    return success(data={
        'honors': [_serialize_honor(h) for h in honors],
        'category_choices': CATEGORY_CHOICES,
    })


@router.post('/honor')
def api_create_honor(request, payload: dict):
    user = request.user
    if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
        return error(msg='您没有权限执行此操作。', code=403)

    student_id = payload.get('student_id', '').strip()
    title = payload.get('title', '').strip()
    category = payload.get('category', 'other')
    level = payload.get('level', '院级')
    description = payload.get('description', '')
    awarded_at = payload.get('awarded_at', '')

    if not student_id:
        return error(msg='请输入学号。', code=400)
    if not title:
        return error(msg='请输入奖项名称。', code=400)

    target_user = User.objects.filter(student_id=student_id).first()
    if not target_user:
        return error(msg=f'未找到学号为 {student_id} 的学生。', code=404)

    honor = Honor.objects.create(
        user=target_user,
        title=title,
        category=category if category in dict(CATEGORY_CHOICES) else 'other',
        level=level,
        description=description,
        awarded_at=awarded_at or timezone.now().date(),
    )
    return success(data=_serialize_honor(honor), msg=f'已录入荣誉：{title}')


@router.delete('/honor/{pk}')
def api_delete_honor(request, pk: int):
    user = request.user
    if not user.is_authenticated or user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
        return error(msg='您没有权限执行此操作。', code=403)

    honor = get_object_or_404(Honor, pk=pk)
    honor_title = honor.title
    honor.delete()
    return success(msg=f'已删除荣誉：{honor_title}')
