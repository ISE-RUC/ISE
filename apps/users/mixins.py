from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    """
    用法：在视图中设置 required_role = User.ROLE_ADMIN
    表示"该角色及以上"才能访问。
    """
    required_role = None

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if self.required_role and request.user.is_authenticated:
            if request.user.role > self.required_role:
                raise PermissionDenied
        return response
