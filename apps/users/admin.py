from django.contrib import admin

from .models import AuditLog, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "real_name",
        "student_id",
        "employee_id",
        "role",
        "grade",
        "major",
        "is_active",
    )
    list_filter = ("role", "grade", "major", "is_active")
    search_fields = ("username", "real_name", "student_id", "employee_id", "email")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "target_model", "target_id", "ip_address", "created_at")
    list_filter = ("action", "target_model", "created_at")
    search_fields = ("user__username", "user__real_name", "action", "target_id", "detail")
