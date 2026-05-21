from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    """
    党团模块本地权限基类。
    仅在当前模块内部使用，避免为迁移最小运行依赖而改动 users 模块。
    """

    required_role = None

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if self.required_role and request.user.is_authenticated:
            if request.user.role > self.required_role:
                raise PermissionDenied
        return response
