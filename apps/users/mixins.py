from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    required_role = None
    permission_denied_message = "您没有权限访问该页面。"

    def has_role_permission(self):
        return (
            self.required_role is None
            or (
                self.request.user.is_authenticated
                and self.request.user.role <= self.required_role
            )
        )

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and not self.has_role_permission():
            raise PermissionDenied(self.permission_denied_message)
        return response


class AdminOrAboveRequiredMixin(RoleRequiredMixin):
    required_role = 2


class CadreOrAboveRequiredMixin(RoleRequiredMixin):
    required_role = 3
