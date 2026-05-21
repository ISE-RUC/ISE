from pathlib import Path

from django import forms

from .models import (
    PartyApprovalTask,
    PartyMaterialSubmission,
    PartyMaterialType,
    PartyStageDefinition,
    PartyStageMaterialRequirement,
)
from .services import workflow


class PartyMaterialSubmissionForm(forms.ModelForm):
    class Meta:
        model = PartyMaterialSubmission
        fields = ["material_type", "file"]

    def __init__(self, *args, stage_instance=None, submitted_by=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_instance = stage_instance
        self.submitted_by = submitted_by
        if self.stage_instance is not None:
            self.fields["material_type"].queryset = workflow.get_stage_material_types(
                self.stage_instance
            )

    def clean(self):
        cleaned_data = super().clean()
        if self.stage_instance is None:
            raise forms.ValidationError("缺少当前流程节点，无法提交材料。")

        material_type = cleaned_data.get("material_type")
        if material_type is None:
            return cleaned_data

        if not workflow.stage_allows_material_type(self.stage_instance, material_type):
            raise forms.ValidationError("当前节点不允许提交该材料类型。")
        return cleaned_data

    def clean_file(self):
        upload = self.cleaned_data.get("file")
        if upload is None:
            return upload

        material_type = self.cleaned_data.get("material_type")
        if material_type is not None:
            extension = Path(upload.name).suffix.lower().lstrip(".")
            allowed_extensions = workflow.parse_allowed_extensions(
                material_type.allowed_extensions
            )
            if allowed_extensions and extension not in allowed_extensions:
                raise forms.ValidationError(
                    f"仅支持以下文件格式：{', '.join(sorted(allowed_extensions))}"
                )

            max_size = material_type.max_size_mb * 1024 * 1024
            if upload.size > max_size:
                raise forms.ValidationError(
                    f"文件大小不能超过 {material_type.max_size_mb}MB。"
                )
        return upload

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.stage_instance = self.stage_instance
        instance.submitted_by = self.submitted_by
        instance.version = workflow.get_next_material_version(
            self.stage_instance,
            instance.material_type,
        )
        if commit:
            instance.save()
        return instance


class PartyApprovalSubmitForm(forms.Form):
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, stage_instance=None, operator=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_instance = stage_instance
        self.operator = operator

    def clean(self):
        cleaned_data = super().clean()
        if self.stage_instance is None:
            raise forms.ValidationError("缺少当前节点，无法提交审批。")
        workflow.validate_submission_ready(self.stage_instance)
        return cleaned_data


class PartyApprovalDecisionForm(forms.Form):
    ACTION_APPROVE = "approve"
    ACTION_REJECT = "reject"
    ACTION_CHOICES = (
        (ACTION_APPROVE, "通过"),
        (ACTION_REJECT, "驳回"),
    )

    action = forms.ChoiceField(choices=ACTION_CHOICES)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, task=None, operator=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.task = task
        self.operator = operator

    def clean(self):
        cleaned_data = super().clean()
        if self.task is None or not isinstance(self.task, PartyApprovalTask):
            raise forms.ValidationError("缺少审批任务，无法处理。")
        if cleaned_data.get("action") == self.ACTION_REJECT and not cleaned_data.get(
            "comment"
        ):
            self.add_error("comment", "驳回时必须填写原因。")
        return cleaned_data


class PartyBatchApprovalForm(forms.Form):
    ACTION_APPROVE = PartyApprovalDecisionForm.ACTION_APPROVE
    ACTION_REJECT = PartyApprovalDecisionForm.ACTION_REJECT
    ACTION_CHOICES = PartyApprovalDecisionForm.ACTION_CHOICES

    task_ids = forms.MultipleChoiceField(
        required=True,
        widget=forms.MultipleHiddenInput,
        error_messages={"required": "请至少选择一条待审批任务。"},
    )
    action = forms.ChoiceField(choices=ACTION_CHOICES)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, task_queryset=None, operator=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.operator = operator
        self.task_queryset = list(task_queryset or [])
        self.fields["task_ids"].choices = [
            (str(task.pk), f"task-{task.pk}") for task in self.task_queryset
        ]

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("action") == self.ACTION_REJECT and not cleaned_data.get(
            "comment"
        ):
            self.add_error("comment", "批量驳回时必须填写原因。")
        return cleaned_data

    def get_tasks(self):
        task_map = {str(task.pk): task for task in self.task_queryset}
        return [
            task_map[str(task_id)]
            for task_id in self.cleaned_data.get("task_ids", [])
            if str(task_id) in task_map
        ]


class PartyStageDefinitionForm(forms.ModelForm):
    class Meta:
        model = PartyStageDefinition
        fields = [
            "code",
            "name",
            "track_type",
            "stage",
            "order",
            "min_duration_days",
            "requires_training",
            "target_role_for_approval",
            "is_active",
            "description",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class PartyMaterialTypeForm(forms.ModelForm):
    class Meta:
        model = PartyMaterialType
        fields = [
            "code",
            "name",
            "description",
            "allowed_extensions",
            "max_size_mb",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_allowed_extensions(self):
        value = self.cleaned_data.get("allowed_extensions", "")
        if not value:
            return ""
        return ",".join(
            sorted(
                {
                    item.strip().lower().lstrip(".")
                    for item in value.split(",")
                    if item.strip()
                }
            )
        )


class PartyStageMaterialRequirementForm(forms.ModelForm):
    class Meta:
        model = PartyStageMaterialRequirement
        fields = [
            "stage_definition",
            "material_type",
            "is_required",
            "order",
            "note",
        ]

    def __init__(self, *args, stage_definition=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stage_definition"].queryset = PartyStageDefinition.objects.order_by(
            "track_type",
            "order",
            "id",
        )
        self.fields["material_type"].queryset = PartyMaterialType.objects.order_by("name")
        if stage_definition is not None and not self.is_bound:
            self.fields["stage_definition"].initial = stage_definition


class PartyImportWorkbookForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("仅支持上传 .xlsx 文件。")
        return upload
