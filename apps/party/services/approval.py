from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.users.models import User

from ..models import PartyApprovalAction, PartyApprovalTask, PartyStageInstance
from . import reminder, workflow


def validate_task_can_process(task):
    if task.status != PartyApprovalTask.Status.PENDING:
        raise ValidationError("当前审批任务已处理，不能重复操作。")


def validate_task_can_withdraw(task, operator, comment=""):
    if task.status not in {
        PartyApprovalTask.Status.APPROVED,
        PartyApprovalTask.Status.REJECTED,
    }:
        raise ValidationError("当前审批任务状态不允许撤回。")
    if task.can_withdraw_until is None or task.can_withdraw_until < timezone.now():
        raise ValidationError("当前审批任务已超过撤回时效。")
    if not comment or not comment.strip():
        raise ValidationError("撤回时必须填写说明。")
    if task.processed_at is None:
        raise ValidationError("当前审批任务缺少处理记录，不能撤回。")
    if operator.role != User.ROLE_LEADER and task.assignee_id != operator.id:
        raise ValidationError("仅原审批人或学院领导可以撤回该审批结果。")
    if task.stage_instance.approval_tasks.filter(status=PartyApprovalTask.Status.PENDING).exists():
        raise ValidationError("当前节点已经存在待审批任务，不能重复撤回。")
    if task.status == PartyApprovalTask.Status.REJECTED:
        if task.stage_instance.material_submissions.filter(submitted_at__gt=task.processed_at).exists():
            raise ValidationError("学生在驳回后已经补交新材料，当前结果不能撤回。")


@transaction.atomic
def approve_task(task, operator, comment=""):
    validate_task_can_process(task)

    now = timezone.now()
    task.status = PartyApprovalTask.Status.APPROVED
    task.assignee = operator
    task.comment = comment
    task.processed_at = now
    task.save(update_fields=["status", "assignee", "comment", "processed_at"])
    PartyApprovalAction.objects.create(
        task=task,
        operator=operator,
        action=PartyApprovalAction.Action.APPROVE,
        comment=comment,
    )
    next_instance = workflow.advance_stage_after_approval(task.stage_instance, operator=operator)
    workflow.log_party_action(
        operator,
        "approve party task",
        "PartyApprovalTask",
        task.pk,
        f"审批通过节点 {task.stage_instance.stage_definition.code}",
    )
    return next_instance


@transaction.atomic
def reject_task(task, operator, comment):
    validate_task_can_process(task)
    if not comment:
        raise ValidationError("驳回时必须填写原因。")

    now = timezone.now()
    task.status = PartyApprovalTask.Status.REJECTED
    task.assignee = operator
    task.comment = comment
    task.processed_at = now
    task.save(update_fields=["status", "assignee", "comment", "processed_at"])
    PartyApprovalAction.objects.create(
        task=task,
        operator=operator,
        action=PartyApprovalAction.Action.REJECT,
        comment=comment,
    )

    stage_instance = task.stage_instance
    stage_instance.status = PartyStageInstance.Status.REJECTED
    stage_instance.remark = comment
    stage_instance.save(update_fields=["status", "remark", "updated_at"])
    workflow.log_party_action(
        operator,
        "reject party task",
        "PartyApprovalTask",
        task.pk,
        f"驳回节点 {task.stage_instance.stage_definition.code}",
    )
    reminder.sync_member_reminders(stage_instance.member)
    return stage_instance


@transaction.atomic
def batch_process_tasks(tasks, operator, action, comment=""):
    tasks = list(tasks)
    if not tasks:
        raise ValidationError("请至少选择一条待审批任务。")
    if action not in {PartyApprovalAction.Action.APPROVE, PartyApprovalAction.Action.REJECT}:
        raise ValidationError("不支持的批量审批操作。")
    if action == PartyApprovalAction.Action.REJECT and not comment:
        raise ValidationError("批量驳回时必须填写原因。")

    for task in tasks:
        validate_task_can_process(task)

    results = []
    for task in tasks:
        if action == PartyApprovalAction.Action.APPROVE:
            results.append(approve_task(task, operator, comment=comment))
        else:
            results.append(reject_task(task, operator, comment=comment))

    task_ids = ",".join(str(task.pk) for task in tasks[:10])
    task_suffix = "" if len(tasks) <= 10 else "..."
    workflow.log_party_action(
        operator,
        f"batch {action} party tasks",
        "PartyApprovalTask",
        "",
        f"批量处理 {len(tasks)} 条审批任务：{task_ids}{task_suffix}",
    )
    return results


@transaction.atomic
def withdraw_task(task, operator, comment=""):
    validate_task_can_withdraw(task, operator, comment=comment)

    now = timezone.now()
    stage_instance = task.stage_instance
    member = stage_instance.member

    if task.status == PartyApprovalTask.Status.APPROVED:
        next_stage_definition = workflow.get_next_stage_definition(stage_instance.stage_definition)
        if next_stage_definition is not None:
            next_stage_instance = (
                PartyStageInstance.objects.filter(
                    member=member,
                    stage_definition=next_stage_definition,
                )
                .prefetch_related("material_submissions", "approval_tasks")
                .first()
            )
            if next_stage_instance is not None:
                if (
                    next_stage_instance.material_submissions.exists()
                    or next_stage_instance.approval_tasks.exists()
                ):
                    raise ValidationError("下一节点已经产生办理数据，当前结果不能撤回。")
                next_stage_instance.delete()

        stage_instance.status = PartyStageInstance.Status.SUBMITTED
        stage_instance.completed_at = None
        stage_instance.save(update_fields=["status", "completed_at", "updated_at"])

    else:
        stage_instance.status = PartyStageInstance.Status.SUBMITTED
        stage_instance.remark = ""
        stage_instance.save(update_fields=["status", "remark", "updated_at"])

    task.status = PartyApprovalTask.Status.WITHDRAWN
    task.assignee = operator
    task.comment = comment
    task.processed_at = now
    task.save(update_fields=["status", "assignee", "comment", "processed_at"])
    PartyApprovalAction.objects.create(
        task=task,
        operator=operator,
        action=PartyApprovalAction.Action.WITHDRAW,
        comment=comment,
    )

    reopened_task = PartyApprovalTask.objects.create(
        stage_instance=stage_instance,
        assignee_role=task.assignee_role,
        status=PartyApprovalTask.Status.PENDING,
        comment="撤回后重新待审",
        can_withdraw_until=now + timezone.timedelta(days=1),
    )
    PartyApprovalAction.objects.create(
        task=reopened_task,
        operator=operator,
        action=PartyApprovalAction.Action.REOPEN,
        comment=f"原审批结果已撤回，重新待审。撤回说明：{comment}",
    )

    member.current_stage = stage_instance.stage_definition.stage
    member.status_since = (stage_instance.started_at or now).date()
    member.expected_next_date = stage_instance.due_at.date() if stage_instance.due_at else None
    member.save(
        update_fields=["current_stage", "status_since", "expected_next_date", "updated_at"]
    )

    workflow.log_party_action(
        operator,
        "withdraw party task",
        "PartyApprovalTask",
        task.pk,
        f"撤回节点 {stage_instance.stage_definition.code} 的审批结果",
    )
    reminder.sync_member_reminders(member)
    return reopened_task
