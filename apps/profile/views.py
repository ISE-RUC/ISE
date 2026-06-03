from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView

from apps.users.models import User


class IndexView(LoginRequiredMixin, TemplateView):
    """个人信息维护页。"""

    template_name = "profile/index.html"
    editable_fields = ("real_name", "student_id", "employee_id", "grade", "major", "email")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile_user"] = self.request.user
        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        student_id = request.POST.get("student_id", "").strip()
        employee_id = request.POST.get("employee_id", "").strip()
        if student_id and User.objects.exclude(pk=user.pk).filter(student_id=student_id).exists():
            messages.error(request, "该学号已被其他账号使用。")
            return redirect("profile:index")
        if employee_id and User.objects.exclude(pk=user.pk).filter(employee_id=employee_id).exists():
            messages.error(request, "该教职工号已被其他账号使用。")
            return redirect("profile:index")
        for field in self.editable_fields:
            if field in request.POST:
                setattr(user, field, request.POST.get(field, "").strip())
        if user.role in (user.ROLE_STUDENT, user.ROLE_CADRE):
            user.employee_id = ""
        elif user.role in (user.ROLE_ADMIN, user.ROLE_LEADER):
            user.student_id = ""
        user.save(update_fields=self.editable_fields)
        messages.success(request, "个人信息已更新。")
        return redirect("profile:index")
