from django import forms
from django.contrib.auth import authenticate
from django.db import transaction

from apps.party.services.profile import ensure_party_profile_for_user
from apps.users.models import User


class LoginForm(forms.Form):
    username = forms.CharField(
        label="用户名/学号/教职工号",
        max_length=150,
        widget=forms.TextInput(attrs={"autofocus": True}),
    )
    password = forms.CharField(
        label="密码",
        strip=False,
        widget=forms.PasswordInput,
    )
    next = forms.CharField(widget=forms.HiddenInput, required=False)

    error_messages = {
        "invalid_login": "用户名、学号、教职工号或密码错误",
        "inactive": "当前账号已被停用",
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        account = (cleaned_data.get("username") or "").strip()
        password = cleaned_data.get("password")
        if not account or not password:
            return cleaned_data

        user = User.objects.filter(username=account).first()
        if user is None:
            user = User.objects.filter(student_id=account).first()
        if user is None:
            user = User.objects.filter(employee_id=account).first()

        username = user.username if user else account
        self.user_cache = authenticate(
            self.request,
            username=username,
            password=password,
        )
        if self.user_cache is None:
            raise forms.ValidationError(self.error_messages["invalid_login"])
        if not self.user_cache.is_active:
            raise forms.ValidationError(self.error_messages["inactive"])
        return cleaned_data

    def get_user(self):
        return self.user_cache


class StudentRegisterForm(forms.ModelForm):
    role = forms.ChoiceField(label="身份类型", choices=User.ROLE_CHOICES)
    student_id = forms.CharField(label="学号", required=False)
    employee_id = forms.CharField(label="教职工号", required=False)
    password1 = forms.CharField(
        label="密码",
        strip=False,
        widget=forms.PasswordInput,
        min_length=8,
    )
    password2 = forms.CharField(
        label="确认密码",
        strip=False,
        widget=forms.PasswordInput,
        min_length=8,
    )

    class Meta:
        model = User
        fields = ["role", "real_name", "student_id", "employee_id"]
        labels = {
            "real_name": "姓名",
            "student_id": "学号",
            "employee_id": "教职工号",
        }

    def clean_role(self):
        role = int(self.cleaned_data.get("role") or User.ROLE_STUDENT)
        if role not in {choice[0] for choice in User.ROLE_CHOICES}:
            raise forms.ValidationError("请选择有效的身份类型")
        return role

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        student_id = (cleaned_data.get("student_id") or "").strip()
        employee_id = (cleaned_data.get("employee_id") or "").strip()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if role in (User.ROLE_STUDENT, User.ROLE_CADRE):
            if not student_id:
                self.add_error("student_id", "该身份必须填写学号")
            if student_id:
                if User.objects.filter(student_id=student_id).exists():
                    self.add_error("student_id", "该学号已注册")
                if User.objects.filter(username=student_id).exists():
                    self.add_error("student_id", "该学号已被占用")
            cleaned_data["employee_id"] = ""

        if role in (User.ROLE_ADMIN, User.ROLE_LEADER):
            if not employee_id:
                self.add_error("employee_id", "该身份必须填写教职工号")
            if employee_id:
                if User.objects.filter(employee_id=employee_id).exists():
                    self.add_error("employee_id", "该教职工号已注册")
                if User.objects.filter(username=employee_id).exists():
                    self.add_error("employee_id", "该教职工号已被占用")
            cleaned_data["student_id"] = ""

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "两次输入的密码不一致")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data["role"]
        student_id = (self.cleaned_data.get("student_id") or "").strip()
        employee_id = (self.cleaned_data.get("employee_id") or "").strip()
        user.role = role
        user.student_id = student_id or None
        user.employee_id = employee_id or None
        user.username = student_id if role in (User.ROLE_STUDENT, User.ROLE_CADRE) else employee_id
        user.set_password(self.cleaned_data["password1"])
        if commit:
            with transaction.atomic():
                user.save()
                ensure_party_profile_for_user(user)
        return user
