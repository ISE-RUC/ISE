from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import TemplateView


class HomeView(TemplateView):
    """首页，当前用于未登录访问的项目入口页。"""

    template_name = "home.html"


class UserLoginView(LoginView):
    """统一登录入口。"""

    template_name = "users/login.html"
    redirect_authenticated_user = True


class UserLogoutView(LogoutView):
    """统一退出入口。"""

    next_page = reverse_lazy("users:home")
