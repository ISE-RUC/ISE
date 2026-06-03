from django import forms
from django.contrib.auth import authenticate

from .models import User


class LoginForm(forms.Form):
    username = forms.CharField(label="用户名/学号/教职工号")
    password = forms.CharField(label="密码", widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        account = (cleaned_data.get("username") or "").strip()
        password = cleaned_data.get("password")
        username = account
        if account and password:
            matched = (
                User.objects.filter(username=account).first()
                or User.objects.filter(student_id=account).first()
                or User.objects.filter(employee_id=account).first()
            )
            if matched:
                username = matched.username
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError("账号或密码错误")
            if not self.user_cache.is_active:
                raise forms.ValidationError("账号已停用")
        return cleaned_data

    def get_user(self):
        return self.user_cache


class StudentRegisterForm(forms.ModelForm):
    password1 = forms.CharField(label="密码", widget=forms.PasswordInput)
    password2 = forms.CharField(label="确认密码", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["role", "real_name", "student_id", "employee_id"]

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        student_id = (cleaned_data.get("student_id") or "").strip()
        employee_id = (cleaned_data.get("employee_id") or "").strip()
        password1 = cleaned_data.get("password1") or ""
        password2 = cleaned_data.get("password2") or ""

        if role in (User.ROLE_STUDENT, User.ROLE_CADRE):
            if not student_id:
                self.add_error("student_id", "学生或班团骨干必须填写学号")
            cleaned_data["employee_id"] = ""
        elif role in (User.ROLE_ADMIN, User.ROLE_LEADER):
            if not employee_id:
                self.add_error("employee_id", "老师或领导必须填写教职工号")
            cleaned_data["student_id"] = ""
        else:
            self.add_error("role", "请选择有效身份")

        if password1 != password2:
            self.add_error("password2", "两次输入的密码不一致")
        if len(password1) < 8:
            self.add_error("password1", "密码长度不能少于8位")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        account = user.student_id or user.employee_id or user.username
        user.username = account
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user
