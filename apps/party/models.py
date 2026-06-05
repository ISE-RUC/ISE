from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.users.models import User


class PartyMemberStatus(models.Model):
    class TrackType(models.TextChoices):
        PARTY = "party", "入党流程"
        LEAGUE = "league", "入团流程"

    class Stage(models.TextChoices):
        APPLICANT = "applicant", "申请人"
        ACTIVIST = "activist", "积极分子"
        CANDIDATE = "candidate", "发展对象"
        PROBATIONARY = "probationary", "预备党员"
        FULL = "full", "正式党员"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="party_profile",
        verbose_name="学生",
    )
    track_type = models.CharField(
        "流程类型",
        max_length=20,
        choices=TrackType.choices,
        default=TrackType.PARTY,
    )
    current_stage = models.CharField(
        "当前阶段",
        max_length=20,
        choices=Stage.choices,
        default=Stage.APPLICANT,
    )
    status_since = models.DateField("进入当前阶段日期", null=True, blank=True)
    expected_next_date = models.DateField("预计下一节点日期", null=True, blank=True)
    is_locked = models.BooleanField("流程锁定", default=False)
    notes = models.TextField("备注", blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_party_profiles",
        verbose_name="创建人",
    )
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "党团发展档案"
        verbose_name_plural = "党团发展档案"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.real_name or self.user.username} - {self.get_current_stage_display()}"

    def clean(self):
        super().clean()
        if self.user and self.user.role not in {User.ROLE_STUDENT, User.ROLE_CADRE}:
            raise ValidationError("党团发展档案默认仅绑定普通学生或班团骨干角色。")


class PartyStageDefinition(models.Model):
    class ApprovalRole(models.IntegerChoices):
        LEADER = User.ROLE_LEADER, "学院领导"
        ADMIN = User.ROLE_ADMIN, "管理老师"
        CADRE = User.ROLE_CADRE, "班团骨干"

    code = models.CharField("节点编码", max_length=50)
    name = models.CharField("节点名称", max_length=100)
    track_type = models.CharField(
        "流程类型",
        max_length=20,
        choices=PartyMemberStatus.TrackType.choices,
        default=PartyMemberStatus.TrackType.PARTY,
    )
    stage = models.CharField(
        "对应阶段",
        max_length=20,
        choices=PartyMemberStatus.Stage.choices,
    )
    order = models.PositiveIntegerField("排序")
    min_duration_days = models.PositiveIntegerField("最短停留天数", default=0)
    requires_training = models.BooleanField("是否要求培训合格", default=False)
    target_role_for_approval = models.IntegerField(
        "审批角色",
        choices=ApprovalRole.choices,
        default=ApprovalRole.ADMIN,
    )
    is_active = models.BooleanField("是否启用", default=True)
    description = models.TextField("节点说明", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "流程节点定义"
        verbose_name_plural = "流程节点定义"
        ordering = ["track_type", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["track_type", "code"], name="uniq_party_stage_def_track_code"
            ),
            models.UniqueConstraint(
                fields=["track_type", "order"], name="uniq_party_stage_def_track_order"
            ),
        ]

    def __str__(self):
        return f"{self.get_track_type_display()} - {self.name}"


class PartyMaterialType(models.Model):
    code = models.CharField("材料类型编码", max_length=50, unique=True)
    name = models.CharField("材料类型名称", max_length=100)
    description = models.TextField("说明", blank=True)
    allowed_extensions = models.CharField(
        "允许后缀",
        max_length=200,
        blank=True,
        help_text="多个后缀使用英文逗号分隔，例如 pdf,doc,docx",
    )
    max_size_mb = models.PositiveIntegerField("大小上限(MB)", default=30)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "材料类型"
        verbose_name_plural = "材料类型"
        ordering = ["name"]

    def __str__(self):
        return self.name


class PartyStageMaterialRequirement(models.Model):
    stage_definition = models.ForeignKey(
        PartyStageDefinition,
        on_delete=models.CASCADE,
        related_name="material_requirements",
        verbose_name="流程节点",
    )
    material_type = models.ForeignKey(
        PartyMaterialType,
        on_delete=models.CASCADE,
        related_name="stage_requirements",
        verbose_name="材料类型",
    )
    is_required = models.BooleanField("是否必需", default=True)
    note = models.CharField("提交说明", max_length=200, blank=True)
    order = models.PositiveIntegerField("排序", default=1)

    class Meta:
        verbose_name = "节点材料要求"
        verbose_name_plural = "节点材料要求"
        ordering = ["stage_definition", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["stage_definition", "material_type"],
                name="uniq_party_stage_material_requirement",
            ),
        ]

    def __str__(self):
        return f"{self.stage_definition.name} - {self.material_type.name}"


class PartyStageInstance(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待开始"
        OPEN = "open", "进行中"
        SUBMITTED = "submitted", "已提交审批"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已驳回"
        WITHDRAWN = "withdrawn", "已撤回"

    member = models.ForeignKey(
        PartyMemberStatus,
        on_delete=models.CASCADE,
        related_name="stage_instances",
        verbose_name="党团发展档案",
    )
    stage_definition = models.ForeignKey(
        PartyStageDefinition,
        on_delete=models.PROTECT,
        related_name="instances",
        verbose_name="节点定义",
    )
    status = models.CharField(
        "节点状态",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    due_at = models.DateTimeField("截止时间", null=True, blank=True)
    completed_at = models.DateTimeField("完成时间", null=True, blank=True)
    remark = models.TextField("备注", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "节点实例"
        verbose_name_plural = "节点实例"
        ordering = ["member", "stage_definition__order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["member", "stage_definition"], name="uniq_party_stage_instance"
            ),
        ]

    def __str__(self):
        return f"{self.member} - {self.stage_definition.name}"

    @property
    def is_overdue(self):
        return bool(self.due_at and self.status in {self.Status.OPEN, self.Status.SUBMITTED} and self.due_at < timezone.now())


class PartyMaterialSubmission(models.Model):
    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "待审核"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已驳回"

    stage_instance = models.ForeignKey(
        PartyStageInstance,
        on_delete=models.CASCADE,
        related_name="material_submissions",
        verbose_name="节点实例",
    )
    material_type = models.ForeignKey(
        PartyMaterialType,
        on_delete=models.PROTECT,
        related_name="submissions",
        verbose_name="材料类型",
    )
    file = models.FileField("材料文件", upload_to="party/materials/")
    version = models.PositiveIntegerField("版本号", default=1)
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_party_materials",
        verbose_name="提交人",
    )
    submitted_at = models.DateTimeField("提交时间", auto_now_add=True)
    review_status = models.CharField(
        "审核状态",
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_party_materials",
        verbose_name="审核人",
    )
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)
    review_comment = models.TextField("审核意见", blank=True)

    class Meta:
        verbose_name = "材料提交"
        verbose_name_plural = "材料提交"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.stage_instance} - {self.material_type.name} - v{self.version}"


class PartyApprovalTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待审批"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已驳回"
        WITHDRAWN = "withdrawn", "已撤回"

    stage_instance = models.ForeignKey(
        PartyStageInstance,
        on_delete=models.CASCADE,
        related_name="approval_tasks",
        verbose_name="节点实例",
    )
    assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="party_approval_tasks",
        verbose_name="审批人",
    )
    assignee_role = models.IntegerField(
        "审批角色",
        choices=PartyStageDefinition.ApprovalRole.choices,
        default=PartyStageDefinition.ApprovalRole.ADMIN,
    )
    status = models.CharField(
        "任务状态",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    comment = models.TextField("审批意见", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    processed_at = models.DateTimeField("处理时间", null=True, blank=True)
    can_withdraw_until = models.DateTimeField("可撤回截止时间", null=True, blank=True)

    class Meta:
        verbose_name = "审批任务"
        verbose_name_plural = "审批任务"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.stage_instance} - {self.get_status_display()}"


class PartyApprovalAction(models.Model):
    class Action(models.TextChoices):
        SUBMIT = "submit", "提交审批"
        APPROVE = "approve", "通过"
        REJECT = "reject", "驳回"
        WITHDRAW = "withdraw", "撤回"
        REOPEN = "reopen", "重开"

    task = models.ForeignKey(
        PartyApprovalTask,
        on_delete=models.CASCADE,
        related_name="actions",
        verbose_name="审批任务",
    )
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="party_approval_actions",
        verbose_name="操作人",
    )
    action = models.CharField("动作", max_length=20, choices=Action.choices)
    comment = models.TextField("说明", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "审批动作记录"
        verbose_name_plural = "审批动作记录"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.task_id} - {self.get_action_display()}"


class PartyReminder(models.Model):
    class ReminderType(models.TextChoices):
        MATERIAL_DUE = "material_due", "材料截止提醒"
        STAGE_READY = "stage_ready", "节点可推进提醒"
        APPROVAL_PENDING = "approval_pending", "审批待办提醒"
        OVERDUE = "overdue", "逾期提醒"

    class Channel(models.TextChoices):
        SITE = "site", "站内"
        EMAIL = "email", "邮件"
        WECHAT = "wechat", "微信"

    class Status(models.TextChoices):
        PENDING = "pending", "待发送"
        SENT = "sent", "已发送"
        FAILED = "failed", "发送失败"
        CANCELED = "canceled", "已取消"

    member = models.ForeignKey(
        PartyMemberStatus,
        on_delete=models.CASCADE,
        related_name="reminders",
        verbose_name="党团发展档案",
    )
    stage_instance = models.ForeignKey(
        PartyStageInstance,
        on_delete=models.CASCADE,
        related_name="reminders",
        null=True,
        blank=True,
        verbose_name="节点实例",
    )
    reminder_type = models.CharField("提醒类型", max_length=30, choices=ReminderType.choices)
    channel = models.CharField("渠道", max_length=20, choices=Channel.choices, default=Channel.SITE)
    status = models.CharField("发送状态", max_length=20, choices=Status.choices, default=Status.PENDING)
    title = models.CharField("提醒标题", max_length=200)
    content = models.TextField("提醒内容", blank=True)
    scheduled_at = models.DateTimeField("计划发送时间")
    sent_at = models.DateTimeField("实际发送时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "流程提醒"
        verbose_name_plural = "流程提醒"
        ordering = ["-scheduled_at"]

    def __str__(self):
        return self.title
