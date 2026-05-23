from django.contrib import admin

from .models import Notification, NotificationRead


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "publisher", "target_grade", "target_major", "target_role", "created_at")
    list_filter = ("target_role", "target_grade", "target_major", "created_at")
    search_fields = ("title", "content", "publisher__username", "publisher__real_name")


@admin.register(NotificationRead)
class NotificationReadAdmin(admin.ModelAdmin):
    list_display = ("id", "notification", "user", "read_at")
    list_filter = ("read_at",)
    search_fields = ("notification__title", "user__username", "user__real_name")
