from django.contrib.auth import login, logout, update_session_auth_hash
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.security import django_auth

from utils.response import error, success

from .forms import LoginForm, StudentRegisterForm
from .models import User


router = Router(tags=["User auth"])


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


class UpdateProfileIn(Schema):
    real_name: str = ""
    grade: str = ""
    major: str = ""
    email: str = ""


class ChangePasswordIn(Schema):
    old_password: str
    new_password1: str
    new_password2: str


def serialize_user(user):
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


@router.get("/me", auth=django_auth)
def api_me(request):
    return success(data=serialize_user(request.user))


@router.post("/login")
def api_login(request, payload: LoginIn):
    form = LoginForm(
        request=request,
        data={"username": payload.username.strip(), "password": payload.password},
    )
    if not form.is_valid():
        first_error = form.non_field_errors()[0] if form.non_field_errors() else "登录失败"
        return error(msg=first_error, code=400)
    login(request, form.get_user())
    return success(data=serialize_user(request.user), msg="登录成功")


@router.post("/register")
def api_register(request, payload: RegisterIn):
    form = StudentRegisterForm(
        data={
            "role": payload.role,
            "real_name": payload.real_name.strip(),
            "student_id": payload.student_id.strip(),
            "employee_id": payload.employee_id.strip(),
            "password1": payload.password1,
            "password2": payload.password2,
        }
    )
    if not form.is_valid():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "注册失败"
        return error(msg=first_error, code=400)
    user = form.save()
    login(request, user)
    return success(data=serialize_user(user), msg="注册成功")


@router.post("/logout", auth=django_auth)
def api_logout(request):
    logout(request)
    return success(data={"logged_out": True}, msg="已退出登录")


@router.post("/me/profile", auth=django_auth)
def api_update_profile(request, payload: UpdateProfileIn):
    user = request.user
    user.real_name = payload.real_name.strip()
    user.grade = payload.grade.strip()
    user.major = payload.major.strip()
    user.email = payload.email.strip()
    user.save(update_fields=["real_name", "grade", "major", "email"])
    return success(data=serialize_user(user), msg="个人资料更新成功")


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


@router.get("/{user_id}", auth=django_auth)
def api_user_detail(request, user_id: int):
    target = get_object_or_404(User, pk=user_id)
    if not (request.user.is_admin_or_above() or request.user.pk == target.pk):
        return error(msg="您没有权限查看该用户信息", code=403)
    return success(data=serialize_user(target))
