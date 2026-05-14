from django.contrib import admin

from .models import (
    PartyApprovalAction,
    PartyApprovalTask,
    PartyMaterialSubmission,
    PartyMaterialType,
    PartyMemberStatus,
    PartyReminder,
    PartyStageDefinition,
    PartyStageInstance,
    PartyStageMaterialRequirement,
)


@admin.register(PartyMemberStatus)
class PartyMemberStatusAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "track_type",
        "current_stage",
        "status_since",
        "expected_next_date",
        "is_locked",
        "updated_at",
    )
    list_filter = ("track_type", "current_stage", "is_locked")
    search_fields = ("user__username", "user__real_name", "user__student_id")


class PartyStageMaterialRequirementInline(admin.TabularInline):
    model = PartyStageMaterialRequirement
    extra = 0


@admin.register(PartyStageDefinition)
class PartyStageDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "track_type",
        "stage",
        "order",
        "min_duration_days",
        "target_role_for_approval",
        "is_active",
    )
    list_filter = ("track_type", "stage", "target_role_for_approval", "is_active")
    search_fields = ("name", "code")
    inlines = [PartyStageMaterialRequirementInline]


@admin.register(PartyMaterialType)
class PartyMaterialTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "allowed_extensions", "max_size_mb", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(PartyStageInstance)
class PartyStageInstanceAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "stage_definition",
        "status",
        "started_at",
        "due_at",
        "completed_at",
        "updated_at",
    )
    list_filter = ("status", "stage_definition__track_type")
    search_fields = (
        "member__user__username",
        "member__user__real_name",
        "stage_definition__name",
    )


@admin.register(PartyMaterialSubmission)
class PartyMaterialSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "stage_instance",
        "material_type",
        "version",
        "submitted_by",
        "submitted_at",
        "review_status",
    )
    list_filter = ("review_status", "material_type")
    search_fields = (
        "stage_instance__member__user__username",
        "stage_instance__member__user__real_name",
        "material_type__name",
    )


class PartyApprovalActionInline(admin.TabularInline):
    model = PartyApprovalAction
    extra = 0
    readonly_fields = ("operator", "action", "comment", "created_at")


@admin.register(PartyApprovalTask)
class PartyApprovalTaskAdmin(admin.ModelAdmin):
    list_display = (
        "stage_instance",
        "assignee",
        "assignee_role",
        "status",
        "created_at",
        "processed_at",
        "can_withdraw_until",
    )
    list_filter = ("status", "assignee_role")
    search_fields = (
        "stage_instance__member__user__username",
        "stage_instance__member__user__real_name",
        "assignee__username",
        "assignee__real_name",
    )
    inlines = [PartyApprovalActionInline]


@admin.register(PartyApprovalAction)
class PartyApprovalActionAdmin(admin.ModelAdmin):
    list_display = ("task", "operator", "action", "created_at")
    list_filter = ("action",)
    search_fields = (
        "task__stage_instance__member__user__username",
        "task__stage_instance__member__user__real_name",
        "operator__username",
        "operator__real_name",
    )


@admin.register(PartyReminder)
class PartyReminderAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "member",
        "reminder_type",
        "channel",
        "status",
        "scheduled_at",
        "sent_at",
    )
    list_filter = ("reminder_type", "channel", "status")
    search_fields = ("title", "member__user__username", "member__user__real_name")
