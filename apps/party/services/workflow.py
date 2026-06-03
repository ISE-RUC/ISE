from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.users.models import AuditLog

from ..models import (
    PartyApprovalAction,
    PartyApprovalTask,
    PartyMaterialSubmission,
    PartyMaterialType,
    PartyMemberStatus,
    PartyStageDefinition,
    PartyStageInstance,
)


def parse_allowed_extensions(allowed_extensions):
    if not allowed_extensions:
        return set()
    return {
        item.strip().lower().lstrip(".")
        for item in allowed_extensions.split(",")
        if item.strip()
    }


def log_party_action(user, action, target_model="", target_id="", detail=""):
    if user and getattr(user, "is_authenticated", False):
        AuditLog.objects.create(
            user=user,
            action=action,
            target_model=target_model,
            target_id=str(target_id) if target_id else "",
            detail=detail,
        )


def get_stage_definitions(track_type):
    return PartyStageDefinition.objects.filter(
        track_type=track_type,
        is_active=True,
    ).order_by("order", "id")


def get_first_stage_definition(track_type):
    return get_stage_definitions(track_type).first()


def get_next_stage_definition(stage_definition):
    return (
        PartyStageDefinition.objects.filter(
            track_type=stage_definition.track_type,
            is_active=True,
            order__gt=stage_definition.order,
        )
        .order_by("order", "id")
        .first()
    )


def get_current_stage_instance(member):
    return (
        member.stage_instances.select_related("stage_definition")
        .filter(
            status__in=[
                PartyStageInstance.Status.OPEN,
                PartyStageInstance.Status.SUBMITTED,
                PartyStageInstance.Status.REJECTED,
            ]
        )
        .order_by("stage_definition__order", "-updated_at")
        .first()
    )


def get_stage_material_types(stage_instance):
    requirement_ids = stage_instance.stage_definition.material_requirements.values_list(
        "material_type_id", flat=True
    )
    return PartyMaterialType.objects.filter(id__in=requirement_ids, is_active=True).order_by(
        "name"
    )


def stage_allows_material_type(stage_instance, material_type):
    return stage_instance.stage_definition.material_requirements.filter(
        material_type=material_type
    ).exists()


def get_next_material_version(stage_instance, material_type):
    latest = (
        PartyMaterialSubmission.objects.filter(
            stage_instance=stage_instance,
            material_type=material_type,
        )
        .order_by("-version")
        .first()
    )
    return 1 if latest is None else latest.version + 1


def get_material_status(stage_instance):
    requirements = stage_instance.stage_definition.material_requirements.select_related(
        "material_type"
    ).order_by("order", "id")
    latest_submissions = {
        submission.material_type_id: submission
        for submission in PartyMaterialSubmission.objects.filter(
            stage_instance=stage_instance
        )
        .select_related("material_type", "submitted_by")
        .order_by("material_type_id", "-version", "-submitted_at")
    }

    items = []
    all_required_ready = True
    for requirement in requirements:
        submission = latest_submissions.get(requirement.material_type_id)
        ready = submission is not None
        if requirement.is_required and not ready:
            all_required_ready = False
        items.append(
            {
                "requirement": requirement,
                "material_type": requirement.material_type,
                "submission": submission,
                "is_ready": ready,
            }
        )
    return items, all_required_ready


def validate_submission_ready(stage_instance):
    if stage_instance.status not in {
        PartyStageInstance.Status.OPEN,
        PartyStageInstance.Status.REJECTED,
    }:
        raise ValidationError("当前节点状态不允许提交审批。")

    _, all_required_ready = get_material_status(stage_instance)
    if not all_required_ready:
        raise ValidationError("当前节点仍有必需材料未提交。")


@transaction.atomic
def initialize_member_workflow(member, operator=None):
    current_instance = get_current_stage_instance(member)
    if current_instance:
        return current_instance

    first_stage = get_first_stage_definition(member.track_type)
    if first_stage is None:
        raise ValidationError("当前流程还没有配置节点定义。")

    started_at = timezone.now()
    due_at = (
        started_at + timedelta(days=first_stage.min_duration_days)
        if first_stage.min_duration_days
        else None
    )
    stage_instance, created = PartyStageInstance.objects.get_or_create(
        member=member,
        stage_definition=first_stage,
        defaults={
            "status": PartyStageInstance.Status.OPEN,
            "started_at": started_at,
            "due_at": due_at,
        },
    )
    if created:
        member.current_stage = first_stage.stage
        member.status_since = started_at.date()
        member.expected_next_date = due_at.date() if due_at else None
        member.save(update_fields=["current_stage", "status_since", "expected_next_date", "updated_at"])
        log_party_action(
            operator,
            "initialize party workflow",
            "PartyStageInstance",
            stage_instance.pk,
            f"为 {member.user} 初始化节点 {first_stage.code}",
        )
    from . import reminder

    reminder.sync_member_reminders(member)
    return stage_instance


@transaction.atomic
def submit_stage_for_approval(stage_instance, operator, comment=""):
    validate_submission_ready(stage_instance)

    task = (
        stage_instance.approval_tasks.select_related("assignee")
        .filter(status=PartyApprovalTask.Status.PENDING)
        .first()
    )
    if task:
        raise ValidationError("当前节点已经存在待审批任务。")

    now = timezone.now()
    task = PartyApprovalTask.objects.create(
        stage_instance=stage_instance,
        assignee_role=stage_instance.stage_definition.target_role_for_approval,
        status=PartyApprovalTask.Status.PENDING,
        comment=comment,
        can_withdraw_until=now + timedelta(days=1),
    )
    PartyApprovalAction.objects.create(
        task=task,
        operator=operator,
        action=PartyApprovalAction.Action.SUBMIT,
        comment=comment,
    )
    stage_instance.status = PartyStageInstance.Status.SUBMITTED
    stage_instance.save(update_fields=["status", "updated_at"])
    log_party_action(
        operator,
        "submit party approval",
        "PartyApprovalTask",
        task.pk,
        f"提交节点 {stage_instance.stage_definition.code} 审批",
    )
    from . import reminder

    reminder.sync_member_reminders(stage_instance.member)
    return task


@transaction.atomic
def advance_stage_after_approval(stage_instance, operator=None):
    member = stage_instance.member
    next_stage = get_next_stage_definition(stage_instance.stage_definition)
    now = timezone.now()

    stage_instance.status = PartyStageInstance.Status.APPROVED
    if stage_instance.completed_at is None:
        stage_instance.completed_at = now
    stage_instance.save(update_fields=["status", "completed_at", "updated_at"])

    if next_stage is None:
        member.current_stage = stage_instance.stage_definition.stage
        member.status_since = stage_instance.completed_at.date()
        member.expected_next_date = None
        member.save(update_fields=["current_stage", "status_since", "expected_next_date", "updated_at"])
        from . import reminder

        reminder.sync_member_reminders(member)
        return None

    next_due_at = (
        now + timedelta(days=next_stage.min_duration_days)
        if next_stage.min_duration_days
        else None
    )
    next_instance, _ = PartyStageInstance.objects.get_or_create(
        member=member,
        stage_definition=next_stage,
        defaults={
            "status": PartyStageInstance.Status.OPEN,
            "started_at": now,
            "due_at": next_due_at,
        },
    )
    if next_instance.status == PartyStageInstance.Status.PENDING:
        next_instance.status = PartyStageInstance.Status.OPEN
        next_instance.started_at = next_instance.started_at or now
        next_instance.due_at = next_instance.due_at or next_due_at
        next_instance.save(update_fields=["status", "started_at", "due_at", "updated_at"])

    member.current_stage = next_stage.stage
    member.status_since = now.date()
    member.expected_next_date = next_due_at.date() if next_due_at else None
    member.save(update_fields=["current_stage", "status_since", "expected_next_date", "updated_at"])
    log_party_action(
        operator,
        "advance party stage",
        "PartyStageInstance",
        next_instance.pk,
        f"流程推进到节点 {next_stage.code}",
    )
    from . import reminder

    reminder.sync_member_reminders(member)
    return next_instance
