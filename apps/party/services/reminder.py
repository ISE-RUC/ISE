from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..models import PartyApprovalTask, PartyReminder, PartyStageInstance


MATERIAL_DUE_LEAD_DAYS = 3


def _upsert_pending_reminder(
    *,
    member,
    reminder_type,
    title,
    content,
    scheduled_at,
    stage_instance=None,
    channel=PartyReminder.Channel.SITE,
):
    if scheduled_at is None:
        return None

    reminder, created = PartyReminder.objects.get_or_create(
        member=member,
        stage_instance=stage_instance,
        reminder_type=reminder_type,
        channel=channel,
        scheduled_at=scheduled_at,
        defaults={
            "status": PartyReminder.Status.PENDING,
            "title": title,
            "content": content,
        },
    )

    fields_to_update = []
    if reminder.title != title:
        reminder.title = title
        fields_to_update.append("title")
    if reminder.content != content:
        reminder.content = content
        fields_to_update.append("content")
    if reminder.status == PartyReminder.Status.CANCELED:
        reminder.status = PartyReminder.Status.PENDING
        fields_to_update.append("status")
    if fields_to_update:
        reminder.save(update_fields=fields_to_update)
    return reminder if created or fields_to_update else reminder


def cancel_pending_reminders(stage_instance, reminder_types=None):
    queryset = PartyReminder.objects.filter(
        stage_instance=stage_instance,
        status=PartyReminder.Status.PENDING,
    )
    if reminder_types:
        queryset = queryset.filter(reminder_type__in=reminder_types)
    return queryset.update(status=PartyReminder.Status.CANCELED)


def build_stage_reminders(stage_instance):
    member = stage_instance.member
    definition = stage_instance.stage_definition
    reminders = []

    if stage_instance.status in {
        PartyStageInstance.Status.PENDING,
        PartyStageInstance.Status.APPROVED,
        PartyStageInstance.Status.WITHDRAWN,
    }:
        cancel_pending_reminders(stage_instance)
        return reminders

    if stage_instance.status in {
        PartyStageInstance.Status.OPEN,
        PartyStageInstance.Status.REJECTED,
    }:
        cancel_pending_reminders(
            stage_instance,
            reminder_types=[PartyReminder.ReminderType.APPROVAL_PENDING],
        )
        if stage_instance.due_at:
            material_due_at = stage_instance.due_at - timedelta(days=MATERIAL_DUE_LEAD_DAYS)
            reminders.append(
                _upsert_pending_reminder(
                    member=member,
                    stage_instance=stage_instance,
                    reminder_type=PartyReminder.ReminderType.MATERIAL_DUE,
                    title=f"{definition.name} 材料准备提醒",
                    content=(
                        f"请在 {stage_instance.due_at:%Y-%m-%d %H:%M} 前完成 "
                        f"{definition.name} 节点材料准备。"
                    ),
                    scheduled_at=material_due_at,
                )
            )
            reminders.append(
                _upsert_pending_reminder(
                    member=member,
                    stage_instance=stage_instance,
                    reminder_type=PartyReminder.ReminderType.STAGE_READY,
                    title=f"{definition.name} 节点可推进提醒",
                    content=f"{definition.name} 已达到可推进时间，请检查材料后提交审批。",
                    scheduled_at=stage_instance.due_at,
                )
            )
        if stage_instance.is_overdue:
            reminders.append(
                _upsert_pending_reminder(
                    member=member,
                    stage_instance=stage_instance,
                    reminder_type=PartyReminder.ReminderType.OVERDUE,
                    title=f"{definition.name} 已逾期",
                    content=f"{definition.name} 已超过计划时间，请尽快处理当前节点。",
                    scheduled_at=timezone.now(),
                )
            )
        else:
            cancel_pending_reminders(
                stage_instance,
                reminder_types=[PartyReminder.ReminderType.OVERDUE],
            )
        return [item for item in reminders if item is not None]

    if stage_instance.status == PartyStageInstance.Status.SUBMITTED:
        cancel_pending_reminders(
            stage_instance,
            reminder_types=[
                PartyReminder.ReminderType.MATERIAL_DUE,
                PartyReminder.ReminderType.STAGE_READY,
                PartyReminder.ReminderType.OVERDUE,
            ],
        )
        pending_task = (
            stage_instance.approval_tasks.filter(status=PartyApprovalTask.Status.PENDING)
            .order_by("created_at")
            .first()
        )
        if pending_task:
            reminders.append(
                _upsert_pending_reminder(
                    member=member,
                    stage_instance=stage_instance,
                    reminder_type=PartyReminder.ReminderType.APPROVAL_PENDING,
                    title=f"{definition.name} 已提交审批",
                    content="当前节点已提交审批，等待老师处理结果。",
                    scheduled_at=pending_task.created_at,
                )
            )
        return [item for item in reminders if item is not None]

    return reminders


@transaction.atomic
def sync_member_reminders(member):
    generated = []
    stage_instances = member.stage_instances.select_related("stage_definition").all()
    for stage_instance in stage_instances:
        generated.extend(build_stage_reminders(stage_instance))
    return [item for item in generated if item is not None]


def get_student_reminders(member, *, limit=6):
    return (
        member.reminders.filter(
            status__in=[PartyReminder.Status.PENDING, PartyReminder.Status.SENT]
        )
        .select_related("stage_instance__stage_definition")
        .order_by("status", "scheduled_at", "-created_at")[:limit]
    )


def get_all_student_reminders(member):
    return (
        member.reminders.select_related("stage_instance__stage_definition")
        .order_by("status", "scheduled_at", "-created_at")
    )


@transaction.atomic
def generate_all_member_reminders(member_queryset=None):
    if member_queryset is None:
        from ..models import PartyMemberStatus

        member_queryset = PartyMemberStatus.objects.prefetch_related("stage_instances")
    generated_count = 0
    for member in member_queryset:
        generated_count += len(sync_member_reminders(member))
    return generated_count


@transaction.atomic
def mark_due_reminders_as_sent(now=None, *, channel=PartyReminder.Channel.SITE):
    now = now or timezone.now()
    queryset = PartyReminder.objects.filter(
        status=PartyReminder.Status.PENDING,
        channel=channel,
        scheduled_at__lte=now,
    )
    sent_count = 0
    for reminder in queryset:
        reminder.status = PartyReminder.Status.SENT
        reminder.sent_at = now
        reminder.save(update_fields=["status", "sent_at"])
        sent_count += 1
    return sent_count
