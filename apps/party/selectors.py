from django.db.models import Prefetch
from django.utils import timezone

from .models import (
    PartyApprovalTask,
    PartyMemberStatus,
    PartyStageDefinition,
    PartyStageInstance,
)


def get_member_with_related(member_id):
    return (
        PartyMemberStatus.objects.select_related("user", "created_by")
        .prefetch_related(
            Prefetch(
                "stage_instances",
                queryset=PartyStageInstance.objects.select_related("stage_definition")
                .prefetch_related(
                    "material_submissions__material_type",
                    "approval_tasks__actions",
                    "approval_tasks__assignee",
                )
                .order_by("stage_definition__order", "id"),
            ),
            "reminders",
        )
        .get(pk=member_id)
    )


def get_student_member_queryset():
    return PartyMemberStatus.objects.select_related("user").prefetch_related(
        Prefetch(
            "stage_instances",
            queryset=PartyStageInstance.objects.select_related("stage_definition").order_by(
                "stage_definition__order", "id"
            ),
        )
    )


def get_student_party_overview(user):
    return (
        PartyMemberStatus.objects.select_related("user")
        .prefetch_related(
            Prefetch(
                "stage_instances",
                queryset=PartyStageInstance.objects.select_related("stage_definition")
                .prefetch_related("material_submissions__material_type", "approval_tasks")
                .order_by("stage_definition__order", "id"),
            ),
            "reminders__stage_instance__stage_definition",
        )
        .filter(user=user)
        .first()
    )


def get_pending_approval_tasks(for_user=None):
    queryset = (
        PartyApprovalTask.objects.select_related(
            "stage_instance__member__user",
            "stage_instance__stage_definition",
            "assignee",
        )
        .prefetch_related("actions", "stage_instance__material_submissions__material_type")
        .filter(status=PartyApprovalTask.Status.PENDING)
        .order_by("created_at")
    )
    if for_user is not None:
        queryset = queryset.filter(assignee_role=for_user.role)
    return queryset


def get_reversible_approval_tasks(for_user=None):
    queryset = (
        PartyApprovalTask.objects.select_related(
            "stage_instance__member__user",
            "stage_instance__stage_definition",
            "assignee",
        )
        .filter(
            status__in=[
                PartyApprovalTask.Status.APPROVED,
                PartyApprovalTask.Status.REJECTED,
            ],
            can_withdraw_until__gte=timezone.now(),
        )
        .order_by("-processed_at", "-created_at")
    )
    if for_user is not None:
        queryset = queryset.filter(assignee_role=for_user.role)
    return queryset


def get_track_stage_definitions(track_type):
    return PartyStageDefinition.objects.filter(
        track_type=track_type,
        is_active=True,
    ).order_by("order", "id")
