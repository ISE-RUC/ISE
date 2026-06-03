from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView, RedirectView, TemplateView

from apps.users.forms import LoginForm, StudentRegisterForm
from apps.notification.views import get_home_notification_summary


def get_safe_redirect(request, fallback_url):
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


def get_role_home_url(user):
    return reverse("users:home")


class HomeView(LoginRequiredMixin, TemplateView):
    """主页。"""

    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_home_notification_summary(self.request))
        context.update(
            {
                "role_name": self.request.user.get_role_display(),
                "is_admin_or_above": self.request.user.is_admin_or_above(),
                "is_cadre_or_above": self.request.user.is_cadre_or_above(),
            }
        )
        return context


class LandingRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return get_role_home_url(self.request.user)


class LoginView(FormView):
    template_name = "users/login.html"
    form_class = LoginForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next_value"] = self.request.POST.get("next") or self.request.GET.get("next") or ""
        return context

    def form_valid(self, form):
        login(self.request, form.get_user())
        messages.success(self.request, "登录成功")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return get_safe_redirect(self.request, get_role_home_url(self.request.user))


class RegisterView(FormView):
    template_name = "users/register.html"
    form_class = StudentRegisterForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("users:home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next_value"] = self.request.POST.get("next") or self.request.GET.get("next") or ""
        return context

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "注册成功，已自动登录")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return get_safe_redirect(self.request, get_role_home_url(self.request.user))


class LogoutView(RedirectView):
    pattern_name = "users:login"
    permanent = False

    def post(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, "已退出登录")
        return redirect(self.pattern_name)

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)
