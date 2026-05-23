from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView, RedirectView, TemplateView
from ninja import Router, Schema
from ninja.security import django_auth

from apps.users.forms import LoginForm, StudentRegisterForm
from apps.users.models import User
from utils.response import error, success

router = Router()


class LoginIn(Schema):
    username: str
    password: str


class RegisterIn(Schema):
    role: int
    real_name: str
    student_id: str = ""
    employee_id: str = ""
    password1: str
    password2: str


class AdminCreateUserIn(Schema):
    username: str
    password: str
    real_name: str
    role: int
    student_id: str = ""
    employee_id: str = ""
    grade: str = ""
    major: str = ""
    email: str = ""


class UpdateRoleIn(Schema):
    role: int


class UpdateProfileIn(Schema):
    real_name: str = ""
    grade: str = ""
    major: str = ""
    email: str = ""


class ChangePasswordIn(Schema):
    old_password: str
    new_password1: str
    new_password2: str


def _get_safe_redirect(request, fallback_url):
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


def _get_role_home_url(user):
    return reverse("users:home")


def _serialize_current_user(user):
    data = {
        "id": user.id,
        "username": user.username,
        "login_account": user.get_login_account(),
        "student_id": user.student_id or "",
        "employee_id": user.employee_id or "",
        "real_name": user.get_display_name(),
        "role": user.role,
        "role_name": user.get_role_display(),
        "grade": user.grade or "",
        "major": user.major or "",
        "email": user.email or "",
        "is_admin_or_above": user.is_admin_or_above(),
        "is_cadre_or_above": user.is_cadre_or_above(),
        "can_publish_notice": user.can_publish_notice(),
        "can_view_sensitive": user.can_view_sensitive(),
        "default_home": _get_role_home_url(user),
    }
    if user.can_view_sensitive():
        data.update(
            {
                "id_number": user.id_number or "",
                "hometown": user.hometown or "",
                "suspension_record": user.suspension_record or "",
            }
        )
    return data


def _serialize_visible_user(viewer, target):
    data = {
        "id": target.id,
        "username": target.username,
        "login_account": target.get_login_account(),
        "student_id": target.student_id or "",
        "employee_id": target.employee_id or "",
        "real_name": target.get_display_name(),
        "role": target.role,
        "role_name": target.get_role_display(),
        "grade": target.grade or "",
        "major": target.major or "",
        "email": target.email or "",
    }
    if viewer.can_view_sensitive():
        data.update(
            {
                "id_number": target.id_number or "",
                "hometown": target.hometown or "",
                "suspension_record": target.suspension_record or "",
            }
        )
    return data


def _check_admin_permission(user):
    return user.is_authenticated and user.is_admin_or_above()


def _validate_manageable_role(operator, target_role):
    valid_roles = {choice[0] for choice in User.ROLE_CHOICES}
    if target_role not in valid_roles:
        return "无效的角色"
    if operator.role == User.ROLE_ADMIN and target_role == User.ROLE_LEADER:
        return "管理老师不能创建或提升为学院领导"
    return ""


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(
            {
                "role_name": user.get_role_display(),
                "is_admin_or_above": user.is_admin_or_above(),
                "is_cadre_or_above": user.is_cadre_or_above(),
            }
        )
        return context


class LandingRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return _get_role_home_url(self.request.user)


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

    def get_initial(self):
        initial = super().get_initial()
        initial["next"] = self.request.GET.get("next", "")
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next_value"] = self.request.POST.get("next") or self.request.GET.get("next") or ""
        return context

    def form_valid(self, form):
        login(self.request, form.get_user())
        messages.success(self.request, "登录成功")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return _get_safe_redirect(self.request, _get_role_home_url(self.request.user))


class RegisterView(FormView):
    template_name = "users/register.html"
    form_class = StudentRegisterForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("users:home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "注册成功，已自动登录")
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next_value"] = self.request.POST.get("next") or self.request.GET.get("next") or ""
        return context

    def get_success_url(self):
        return _get_safe_redirect(self.request, _get_role_home_url(self.request.user))


class LogoutView(RedirectView):
    pattern_name = "users:login"
    permanent = False

    def post(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, "已退出登录")
        return redirect(self.pattern_name)

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


@router.get("/me", auth=django_auth)
def api_me(request):
    return success(data=_serialize_current_user(request.user))


@router.post("/me/profile", auth=django_auth)
def api_update_profile(request, payload: UpdateProfileIn):
    user = request.user
    user.real_name = (payload.real_name or "").strip()
    user.grade = (payload.grade or "").strip()
    user.major = (payload.major or "").strip()
    user.email = (payload.email or "").strip()
    user.save(update_fields=["real_name", "grade", "major", "email"])
    return success(data=_serialize_current_user(user), msg="个人资料更新成功")


@router.post("/me/password", auth=django_auth)
def api_change_password(request, payload: ChangePasswordIn):
    user = request.user
    if not user.check_password(payload.old_password):
        return error(msg="原密码错误", code=400)
    if payload.new_password1 != payload.new_password2:
        return error(msg="两次输入的新密码不一致", code=400)
    if len(payload.new_password1 or "") < 8:
        return error(msg="新密码长度不能少于8位", code=400)
    user.set_password(payload.new_password1)
    user.save(update_fields=["password"])
    update_session_auth_hash(request, user)
    return success(data={"password_changed": True}, msg="密码修改成功")


@router.post("/login")
def api_login(request, payload: LoginIn):
    form = LoginForm(
        request=request,
        data={
            "username": (payload.username or "").strip(),
            "password": payload.password,
        },
    )
    if not form.is_valid():
        non_field_errors = form.non_field_errors()
        return error(msg=non_field_errors[0] if non_field_errors else "登录失败", code=400)
    login(request, form.get_user())
    return success(data=_serialize_current_user(request.user), msg="登录成功")


@router.post("/register")
def api_register(request, payload: RegisterIn):
    form = StudentRegisterForm(
        data={
            "role": payload.role,
            "real_name": (payload.real_name or "").strip(),
            "student_id": (payload.student_id or "").strip(),
            "employee_id": (payload.employee_id or "").strip(),
            "password1": payload.password1,
            "password2": payload.password2,
        }
    )
    if not form.is_valid():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "注册失败"
        return error(msg=first_error, code=400)
    user = form.save()
    login(request, user)
    return success(data=_serialize_current_user(user), msg="注册成功")


@router.post("/logout", auth=django_auth)
def api_logout(request):
    logout(request)
    return success(data={"logged_out": True}, msg="已退出登录")


@router.get("/list", auth=django_auth)
def api_user_list(request):
    if not _check_admin_permission(request.user):
        return error(msg="您没有权限执行此操作", code=403)
    users = User.objects.order_by("role", "username")
    return success(data=[_serialize_current_user(user) for user in users])


@router.post("/admin/create", auth=django_auth)
def api_admin_create_user(request, payload: AdminCreateUserIn):
    if not _check_admin_permission(request.user):
        return error(msg="您没有权限执行此操作", code=403)

    role_error = _validate_manageable_role(request.user, payload.role)
    if role_error:
        return error(msg=role_error, code=400)

    username = (payload.username or "").strip()
    student_id = (payload.student_id or "").strip()
    employee_id = (payload.employee_id or "").strip()

    if not username:
        return error(msg="用户名不能为空", code=400)
    if User.objects.filter(username=username).exists():
        return error(msg="用户名已存在", code=400)

    if payload.role in (User.ROLE_STUDENT, User.ROLE_CADRE):
        if not student_id:
            return error(msg="该身份必须填写学号", code=400)
        if User.objects.filter(student_id=student_id).exists():
            return error(msg="学号已存在", code=400)
        employee_id = ""

    if payload.role in (User.ROLE_ADMIN, User.ROLE_LEADER):
        if not employee_id:
            return error(msg="该身份必须填写教职工号", code=400)
        if User.objects.filter(employee_id=employee_id).exists():
            return error(msg="教职工号已存在", code=400)
        student_id = ""

    user = User.objects.create_user(
        username=username,
        password=payload.password,
        real_name=(payload.real_name or "").strip(),
        role=payload.role,
        student_id=student_id or None,
        employee_id=employee_id or None,
        grade=(payload.grade or "").strip(),
        major=(payload.major or "").strip(),
        email=(payload.email or "").strip(),
    )
    return success(data=_serialize_current_user(user), msg="账号创建成功")


@router.post("/{user_id}/role", auth=django_auth)
def api_update_user_role(request, user_id: int, payload: UpdateRoleIn):
    if not _check_admin_permission(request.user):
        return error(msg="您没有权限执行此操作", code=403)

    user = get_object_or_404(User, pk=user_id)
    if user.pk == request.user.pk:
        return error(msg="暂不支持修改自己的角色", code=400)

    role_error = _validate_manageable_role(request.user, payload.role)
    if role_error:
        return error(msg=role_error, code=400)

    user.role = payload.role
    user.save(update_fields=["role"])
    return success(data=_serialize_current_user(user), msg="角色更新成功")


@router.get("/{user_id}", auth=django_auth)
def api_user_detail(request, user_id: int):
    target = get_object_or_404(User, pk=user_id)
    if not (_check_admin_permission(request.user) or request.user.pk == target.pk):
        return error(msg="您没有权限查看该用户信息", code=403)
    return success(data=_serialize_visible_user(request.user, target))
