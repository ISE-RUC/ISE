from urllib.parse import urlencode, urlsplit

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.views.generic import TemplateView

from apps.party.forms import (
    PartyBatchApprovalForm,
    PartyApprovalDecisionForm,
    PartyApprovalSubmitForm,
    PartyImportWorkbookForm,
    PartyMaterialSubmissionForm,
    PartyMaterialTypeForm,
    PartyStageDefinitionForm,
    PartyStageMaterialRequirementForm,
)
from apps.party.models import (
    PartyApprovalTask,
    PartyMaterialType,
    PartyMemberStatus,
    PartyReminder,
    PartyStageDefinition,
    PartyStageInstance,
    PartyStageMaterialRequirement,
)
from apps.party.selectors import (
    get_member_with_related,
    get_pending_approval_tasks,
    get_reversible_approval_tasks,
    get_student_member_queryset,
    get_student_party_overview,
    get_track_stage_definitions,
)
from apps.party.services import approval, reminder, workflow
from apps.party.services import import_export
from apps.users.mixins import RoleRequiredMixin
from apps.users.models import User


class IndexView(TemplateView):
    template_name = "party/index.html"


class PartyNavigationMixin:
    back_url_name = "party:index"
    breadcrumb_items = ()
    page_back_label = "返回上一页"

    def _resolve_url(self, target, kwargs=None):
        if not target:
            return ""
        if isinstance(target, str) and target.startswith("/"):
            return target
        return reverse(target, kwargs=kwargs)

    def _get_safe_relative_url(self, candidate):
        if not candidate:
            return None
        if not url_has_allowed_host_and_scheme(
            candidate,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return None
        parsed = urlsplit(candidate)
        if not parsed.path.startswith("/"):
            return None
        relative_url = parsed.path
        if parsed.query:
            relative_url = f"{relative_url}?{parsed.query}"
        if relative_url == self.request.get_full_path():
            return None
        return relative_url

    def get_default_back_url(self):
        return self._resolve_url(self.back_url_name)

    def get_page_back_url(self):
        return (
            self._get_safe_relative_url(self.request.GET.get("return_to"))
            or self._get_safe_relative_url(self.request.META.get("HTTP_REFERER"))
            or self.get_default_back_url()
        )

    def get_breadcrumb_items(self):
        return self.breadcrumb_items

    def get_breadcrumbs(self):
        breadcrumbs = []
        for item in self.get_breadcrumb_items():
            if isinstance(item, dict):
                breadcrumbs.append(item)
                continue
            label = item[0]
            target = item[1] if len(item) > 1 else None
            kwargs = item[2] if len(item) > 2 else None
            breadcrumbs.append(
                {
                    "label": label,
                    "url": self._resolve_url(target, kwargs=kwargs) if target else "",
                }
            )
        return breadcrumbs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("current_page_url", self.request.get_full_path())
        context.setdefault("page_back_url", self.get_page_back_url())
        context.setdefault("page_back_label", self.page_back_label)
        context.setdefault("breadcrumbs", self.get_breadcrumbs())
        return context


class StudentPartyMixin(LoginRequiredMixin, PartyNavigationMixin):
    member = None

    def dispatch(self, request, *args, **kwargs):
        self.member = get_student_party_overview(request.user)
        if self.member:
            workflow.initialize_member_workflow(self.member)
            self.member.refresh_from_db()
        return super().dispatch(request, *args, **kwargs)

    def get_current_stage(self):
        if not self.member:
            return None
        return workflow.get_current_stage_instance(self.member)

    def get_student_base_context(self):
        context = {
            "member": self.member,
            "current_stage_instance": None,
            "student_reminders": [],
        }
        if not self.member:
            return context

        current_stage_instance = self.get_current_stage()
        context["current_stage_instance"] = current_stage_instance
        context["student_reminders"] = reminder.get_student_reminders(self.member)
        if current_stage_instance:
            material_items, all_ready = workflow.get_material_status(current_stage_instance)
            context["material_items"] = material_items
            context["all_materials_ready"] = all_ready
            context["pending_task"] = current_stage_instance.approval_tasks.filter(
                status=PartyApprovalTask.Status.PENDING
            ).first()
        else:
            context["material_items"] = []
            context["all_materials_ready"] = False
            context["pending_task"] = None
        return context


class StudentDashboardView(StudentPartyMixin, TemplateView):
    template_name = "party/student_dashboard.html"
    back_url_name = "party:index"
    breadcrumb_items = (
        ("党团模块", "party:index"),
        ("学生端", None),
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_student_base_context())
        return context


class StudentTimelineView(StudentPartyMixin, TemplateView):
    template_name = "party/student_timeline.html"
    back_url_name = "party:party_student:dashboard"
    breadcrumb_items = (
        ("党团模块", "party:index"),
        ("学生端", "party:party_student:dashboard"),
        ("流程时间轴", None),
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_student_base_context())

        timeline_items = []
        if self.member:
            definitions = list(get_track_stage_definitions(self.member.track_type))
            instances = {
                instance.stage_definition_id: instance
                for instance in self.member.stage_instances.select_related("stage_definition").all()
            }
            current_stage = context.get("current_stage_instance")
            current_order = (
                current_stage.stage_definition.order if current_stage is not None else None
            )
            for definition in definitions:
                instance = instances.get(definition.id)
                if instance:
                    state = "current"
                    if instance.status == PartyStageInstance.Status.APPROVED:
                        state = "done"
                    elif current_stage and instance.id != current_stage.id:
                        state = "done" if definition.order < current_order else "upcoming"
                else:
                    if current_order is None:
                        state = "upcoming"
                    else:
                        state = "done" if definition.order < current_order else "upcoming"
                timeline_items.append(
                    {
                        "definition": definition,
                        "instance": instance,
                        "state": state,
                    }
                )

        context["timeline_items"] = timeline_items
        return context


class StudentMaterialsView(StudentPartyMixin, TemplateView):
    template_name = "party/student_materials.html"
    back_url_name = "party:party_student:dashboard"
    breadcrumb_items = (
        ("党团模块", "party:index"),
        ("学生端", "party:party_student:dashboard"),
        ("材料提交", None),
    )

    def get_material_form(self):
        current_stage = self.get_current_stage()
        return PartyMaterialSubmissionForm(
            stage_instance=current_stage,
            submitted_by=self.request.user,
        )

    def get_submit_form(self):
        current_stage = self.get_current_stage()
        return PartyApprovalSubmitForm(
            stage_instance=current_stage,
            operator=self.request.user,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_student_base_context())
        context.setdefault("material_form", self.get_material_form())
        context.setdefault("submit_form", self.get_submit_form())
        return context

    def post(self, request, *args, **kwargs):
        if not self.member:
            messages.error(request, "当前账号还没有建立党团档案。")
            return redirect("party:party_student:materials")

        current_stage = self.get_current_stage()
        if current_stage is None:
            messages.error(request, "当前没有可办理的流程节点。")
            return redirect("party:party_student:materials")

        action = request.POST.get("action")
        if action == "upload_material":
            material_form = PartyMaterialSubmissionForm(
                request.POST,
                request.FILES,
                stage_instance=current_stage,
                submitted_by=request.user,
            )
            submit_form = self.get_submit_form()
            if material_form.is_valid():
                submission = material_form.save()
                workflow.log_party_action(
                    request.user,
                    "upload party material",
                    "PartyMaterialSubmission",
                    submission.pk,
                    f"上传材料 {submission.material_type.code}",
                )
                messages.success(request, "材料上传成功。")
                return redirect("party:party_student:materials")
            return self.render_to_response(
                self.get_context_data(
                    material_form=material_form,
                    submit_form=submit_form,
                )
            )

        if action == "submit_approval":
            material_form = self.get_material_form()
            submit_form = PartyApprovalSubmitForm(
                request.POST,
                stage_instance=current_stage,
                operator=request.user,
            )
            if submit_form.is_valid():
                try:
                    workflow.submit_stage_for_approval(
                        current_stage,
                        request.user,
                        comment=submit_form.cleaned_data.get("comment", ""),
                    )
                except ValidationError as exc:
                    submit_form.add_error(None, exc.message)
                else:
                    messages.success(request, "当前节点已提交审批。")
                    return redirect("party:party_student:materials")
            return self.render_to_response(
                self.get_context_data(
                    material_form=material_form,
                    submit_form=submit_form,
                )
            )

        messages.error(request, "无法识别的提交动作。")
        return redirect("party:party_student:materials")


class StudentHistoryView(StudentPartyMixin, TemplateView):
    template_name = "party/student_history.html"
    back_url_name = "party:party_student:dashboard"
    breadcrumb_items = (
        ("党团模块", "party:index"),
        ("学生端", "party:party_student:dashboard"),
        ("流程记录", None),
    )

    def _build_task_timeline(self, tasks):
        timeline = []
        for task in tasks:
            actions = list(task.actions.all().order_by("created_at"))
            withdraw_action = next(
                (action for action in actions if action.action == "withdraw"),
                None,
            )
            reopen_action = next(
                (action for action in actions if action.action == "reopen"),
                None,
            )
            timeline.append(
                {
                    "task": task,
                    "actions": actions,
                    "withdraw_action": withdraw_action,
                    "reopen_action": reopen_action,
                    "was_withdrawn": task.status == PartyApprovalTask.Status.WITHDRAWN,
                }
            )
        return timeline

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_student_base_context())

        history_entries = []
        if self.member:
            stage_instances = (
                self.member.stage_instances.select_related("stage_definition")
                .prefetch_related(
                    "material_submissions__material_type",
                    "approval_tasks__actions",
                    "approval_tasks__assignee",
                )
                .order_by("stage_definition__order", "id")
            )
            for stage_instance in stage_instances:
                tasks = list(stage_instance.approval_tasks.all().order_by("created_at"))
                task_timeline = self._build_task_timeline(tasks)
                actions = []
                for task_entry in task_timeline:
                    actions.extend(task_entry["actions"])
                history_entries.append(
                    {
                        "stage_instance": stage_instance,
                        "materials": list(
                            stage_instance.material_submissions.all().order_by(
                                "material_type__name", "-version", "-submitted_at"
                            )
                        ),
                        "tasks": tasks,
                        "task_timeline": task_timeline,
                        "actions": actions,
                    }
                )

        context["history_entries"] = history_entries
        return context


class StudentReminderListView(StudentPartyMixin, TemplateView):
    template_name = "party/student_reminders.html"
    back_url_name = "party:party_student:dashboard"
    breadcrumb_items = (
        ("党团模块", "party:index"),
        ("学生端", "party:party_student:dashboard"),
        ("提醒与待办", None),
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_student_base_context())
        reminder_items = []
        if self.member:
            reminder_items = list(reminder.get_all_student_reminders(self.member))
        context["reminder_items"] = reminder_items
        context["pending_reminder_count"] = sum(
            1 for item in reminder_items if item.status == PartyReminder.Status.PENDING
        )
        context["sent_reminder_count"] = sum(
            1 for item in reminder_items if item.status == PartyReminder.Status.SENT
        )
        return context


class AdminPartyMixin(RoleRequiredMixin, PartyNavigationMixin):
    required_role = User.ROLE_ADMIN


class AdminDashboardView(AdminPartyMixin, TemplateView):
    required_role = User.ROLE_ADMIN
    template_name = "party/admin_dashboard.html"
    back_url_name = "party:index"
    breadcrumb_items = (
        ("党团模块", "party:index"),
        ("管理端", None),
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pending_task_count"] = PartyApprovalTask.objects.filter(
            status=PartyApprovalTask.Status.PENDING,
            assignee_role=self.request.user.role,
        ).count()
        context["pending_reminder_count"] = PartyReminder.objects.filter(
            status=PartyReminder.Status.PENDING
        ).count()
        context["sent_reminder_count"] = PartyReminder.objects.filter(
            status=PartyReminder.Status.SENT
        ).count()
        context["failed_reminder_count"] = PartyReminder.objects.filter(
            status=PartyReminder.Status.FAILED
        ).count()
        context["overdue_stage_count"] = PartyStageInstance.objects.filter(
            status__in=[
                PartyStageInstance.Status.OPEN,
                PartyStageInstance.Status.SUBMITTED,
            ],
            due_at__lt=workflow.timezone.now(),
        ).count()
        return context


class AdminMemberListView(AdminPartyMixin, TemplateView):
    template_name = "party/admin_members.html"
    page_size = 10
    back_url_name = "party:party_admin:dashboard"
    breadcrumb_items = (
        ("党团模块", "party:index"),
        ("管理端", "party:party_admin:dashboard"),
        ("成员列表", None),
    )

    def _build_query_string(self, extra_params=None, *, exclude=None):
        params = self.request.GET.copy()
        for key in exclude or []:
            params.pop(key, None)
        if extra_params:
            for key, value in extra_params.items():
                if value in (None, ""):
                    params.pop(key, None)
                else:
                    params[key] = str(value)
        encoded = params.urlencode()
        return f"&{encoded}" if encoded else ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        stage_filter = self.request.GET.get("stage", "").strip()
        task_filter = self.request.GET.get("task_status", "").strip()
        grade_filter = self.request.GET.get("grade", "").strip()
        major_filter = self.request.GET.get("major", "").strip()
        sort = self.request.GET.get("sort", "updated_desc").strip()
        members = []
        for member in get_student_member_queryset():
            current_stage = workflow.get_current_stage_instance(member)
            pending_count = member.stage_instances.filter(
                approval_tasks__status=PartyApprovalTask.Status.PENDING
            ).distinct().count()
            completed_count = member.stage_instances.filter(
                status=PartyStageInstance.Status.APPROVED
            ).count()
            if query:
                haystack = " ".join(
                    filter(
                        None,
                        [
                            member.user.real_name,
                            member.user.username,
                            member.user.student_id,
                            member.user.major,
                            member.user.grade,
                        ],
                    )
                ).lower()
                if query.lower() not in haystack:
                    continue
            if grade_filter and member.user.grade != grade_filter:
                continue
            if major_filter and major_filter.lower() not in (member.user.major or "").lower():
                continue
            if stage_filter and member.current_stage != stage_filter:
                continue
            if task_filter == "pending" and pending_count == 0:
                continue
            if task_filter == "none" and pending_count > 0:
                continue
            members.append(
                {
                    "member": member,
                    "current_stage_instance": current_stage,
                    "pending_count": pending_count,
                    "completed_count": completed_count,
                }
            )

        sort_map = {
            "updated_desc": lambda row: row["member"].updated_at,
            "updated_asc": lambda row: row["member"].updated_at,
            "name_asc": lambda row: row["member"].user.real_name or row["member"].user.username,
            "name_desc": lambda row: row["member"].user.real_name or row["member"].user.username,
            "pending_desc": lambda row: row["pending_count"],
            "pending_asc": lambda row: row["pending_count"],
            "completed_desc": lambda row: row["completed_count"],
            "completed_asc": lambda row: row["completed_count"],
        }
        if sort not in sort_map:
            sort = "updated_desc"
        reverse = sort.endswith("_desc")
        members.sort(key=sort_map[sort], reverse=reverse)

        paginator = Paginator(members, self.page_size)
        page_obj = paginator.get_page(self.request.GET.get("page") or 1)
        context["member_rows"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["stage_choices"] = PartyMemberStatus.Stage.choices
        context["grade_choices"] = sorted(
            {member.user.grade for member in get_student_member_queryset() if member.user.grade}
        )
        context["current_filters"] = {
            "q": query,
            "stage": stage_filter,
            "task_status": task_filter,
            "grade": grade_filter,
            "major": major_filter,
            "sort": sort,
        }
        context["member_page_query"] = self._build_query_string(exclude=["page"])
        return context


class AdminMemberDetailView(AdminPartyMixin, TemplateView):
    template_name = "party/admin_member_detail.html"
    back_url_name = "party:party_admin:members"

    def _build_task_timeline(self, tasks):
        timeline = []
        for task in tasks:
            actions = list(task.actions.all().order_by("created_at"))
            timeline.append(
                {
                    "task": task,
                    "actions": actions,
                    "withdraw_action": next(
                        (action for action in actions if action.action == "withdraw"),
                        None,
                    ),
                    "reopen_action": next(
                        (action for action in actions if action.action == "reopen"),
                        None,
                    ),
                }
            )
        return timeline

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        member = get_object_or_404(get_student_member_queryset(), pk=self.kwargs["member_id"])
        member = get_member_with_related(member.pk)
        current_stage = workflow.get_current_stage_instance(member)

        definitions = list(get_track_stage_definitions(member.track_type))
        instances = {instance.stage_definition_id: instance for instance in member.stage_instances.all()}
        current_order = current_stage.stage_definition.order if current_stage else None
        timeline_items = []
        for definition in definitions:
            instance = instances.get(definition.id)
            if instance:
                state = "current"
                if instance.status == PartyStageInstance.Status.APPROVED:
                    state = "done"
                elif current_stage and instance.id != current_stage.id:
                    state = "done" if definition.order < current_order else "upcoming"
            else:
                state = "upcoming" if current_order is None else (
                    "done" if definition.order < current_order else "upcoming"
                )
            timeline_items.append({"definition": definition, "instance": instance, "state": state})

        history_entries = []
        for stage_instance in member.stage_instances.all():
            tasks = list(stage_instance.approval_tasks.all().order_by("created_at"))
            history_entries.append(
                {
                    "stage_instance": stage_instance,
                    "materials": list(
                        stage_instance.material_submissions.all().order_by(
                            "material_type__name", "-version", "-submitted_at"
                        )
                    ),
                    "task_timeline": self._build_task_timeline(tasks),
                }
            )

        context.update(
            {
                "member": member,
                "current_stage_instance": current_stage,
                "timeline_items": timeline_items,
                "history_entries": history_entries,
                "member_pending_tasks": member.stage_instances.filter(
                    approval_tasks__status=PartyApprovalTask.Status.PENDING
                ).distinct().count(),
                "member_reversible_tasks": member.stage_instances.filter(
                    approval_tasks__status__in=[
                        PartyApprovalTask.Status.APPROVED,
                        PartyApprovalTask.Status.REJECTED,
                    ],
                    approval_tasks__can_withdraw_until__gte=workflow.timezone.now(),
                ).distinct().count(),
            }
        )
        return context

    def get_breadcrumb_items(self):
        return (
            ("党团模块", "party:index"),
            ("管理端", "party:party_admin:dashboard"),
            ("成员列表", "party:party_admin:members"),
            ("成员详情", None),
        )


class AdminApprovalListView(AdminPartyMixin, TemplateView):
    template_name = "party/admin_approvals.html"
    page_size = 8
    back_url_name = "party:party_admin:dashboard"
    breadcrumb_items = (
        ("党团模块", "party:index"),
        ("管理端", "party:party_admin:dashboard"),
        ("审批工作台", None),
    )

    def _build_query_string(self, extra_params=None, *, exclude=None):
        params = self.request.GET.copy()
        for key in exclude or []:
            params.pop(key, None)
        if extra_params:
            for key, value in extra_params.items():
                if value in (None, ""):
                    params.pop(key, None)
                else:
                    params[key] = str(value)
        encoded = params.urlencode()
        return f"&{encoded}" if encoded else ""

    def _get_task_chain(self, stage_instance):
        tasks = list(
            stage_instance.approval_tasks.prefetch_related("actions", "assignee").order_by(
                "created_at"
            )
        )
        chain = []
        for task in tasks:
            actions = list(task.actions.all().order_by("created_at"))
            chain.append(
                {
                    "task": task,
                    "actions": actions,
                    "withdraw_action": next(
                        (action for action in actions if action.action == "withdraw"),
                        None,
                    ),
                    "reopen_action": next(
                        (action for action in actions if action.action == "reopen"),
                        None,
                    ),
                }
            )
        return chain

    def _get_post_redirect_url(self, request):
        redirect_to = self._get_safe_relative_url(request.POST.get("redirect_to"))
        return redirect_to or reverse("party:party_admin:approvals")

    def _build_task_summary(self, task):
        material_items, all_ready = workflow.get_material_status(task.stage_instance)
        submitted_count = sum(1 for item in material_items if item["submission"])
        total_count = len(material_items)
        member = task.stage_instance.member
        latest_submission = next(
            (
                item["submission"]
                for item in material_items
                if item["submission"] is not None
            ),
            None,
        )
        if latest_submission is None:
            latest_submission = (
                task.stage_instance.material_submissions.order_by("-submitted_at").first()
            )
        pending_task_count = member.stage_instances.filter(
            approval_tasks__status=PartyApprovalTask.Status.PENDING
        ).distinct().count()
        reversible_task_count = member.stage_instances.filter(
            approval_tasks__status__in=[
                PartyApprovalTask.Status.APPROVED,
                PartyApprovalTask.Status.REJECTED,
            ],
            approval_tasks__can_withdraw_until__gte=workflow.timezone.now(),
        ).distinct().count()
        return {
            "task": task,
            "material_items": material_items,
            "all_ready": all_ready,
            "submitted_count": submitted_count,
            "total_count": total_count,
            "latest_submission": latest_submission,
            "is_overdue": task.stage_instance.is_overdue,
            "pending_task_count": pending_task_count,
            "reversible_task_count": reversible_task_count,
            "member_grade": member.user.grade or "--",
            "member_major": member.user.major or "--",
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        member_filter = self.request.GET.get("member", "").strip()
        query = self.request.GET.get("q", "").strip()
        stage_filter = self.request.GET.get("stage", "").strip()
        sort = self.request.GET.get("sort", "created_asc").strip()
        tasks = list(get_pending_approval_tasks(for_user=self.request.user))
        reversible_tasks = list(get_reversible_approval_tasks(for_user=self.request.user))
        if member_filter:
            tasks = [
                task
                for task in tasks
                if str(task.stage_instance.member_id) == member_filter
            ]
            reversible_tasks = [
                task
                for task in reversible_tasks
                if str(task.stage_instance.member_id) == member_filter
            ]
        if query:
            query_lower = query.lower()
            tasks = [
                task for task in tasks
                if query_lower in " ".join(
                    filter(
                        None,
                        [
                            task.stage_instance.member.user.real_name,
                            task.stage_instance.member.user.username,
                            task.stage_instance.member.user.student_id,
                            task.stage_instance.stage_definition.name,
                        ],
                    )
                ).lower()
            ]
            reversible_tasks = [
                task for task in reversible_tasks
                if query_lower in " ".join(
                    filter(
                        None,
                        [
                            task.stage_instance.member.user.real_name,
                            task.stage_instance.member.user.username,
                            task.stage_instance.member.user.student_id,
                            task.stage_instance.stage_definition.name,
                        ],
                    )
                ).lower()
            ]
        if stage_filter:
            tasks = [
                task for task in tasks
                if task.stage_instance.member.current_stage == stage_filter
            ]
            reversible_tasks = [
                task for task in reversible_tasks
                if task.stage_instance.member.current_stage == stage_filter
            ]
        sort_map = {
            "created_asc": lambda task: task.created_at,
            "created_desc": lambda task: task.created_at,
            "student_asc": lambda task: task.stage_instance.member.user.real_name or task.stage_instance.member.user.username,
            "student_desc": lambda task: task.stage_instance.member.user.real_name or task.stage_instance.member.user.username,
            "stage_asc": lambda task: task.stage_instance.stage_definition.order,
            "stage_desc": lambda task: task.stage_instance.stage_definition.order,
        }
        if sort not in sort_map:
            sort = "created_asc"
        reverse = sort.endswith("_desc")
        tasks.sort(key=sort_map[sort], reverse=reverse)
        reversible_tasks.sort(key=sort_map[sort], reverse=reverse)
        selected_task = kwargs.get("selected_task")
        selected_task_id = self.request.GET.get("task")
        all_tasks = tasks + [task for task in reversible_tasks if task not in tasks]
        if selected_task_id:
            for task in all_tasks:
                if str(task.pk) == selected_task_id:
                    selected_task = task
                    break
        if selected_task is None and all_tasks:
            selected_task = all_tasks[0]

        pending_page_obj = Paginator(tasks, self.page_size).get_page(
            self.request.GET.get("pending_page") or 1
        )
        reversible_page_obj = Paginator(reversible_tasks, self.page_size).get_page(
            self.request.GET.get("reversible_page") or 1
        )
        task_summaries = [self._build_task_summary(task) for task in pending_page_obj.object_list]
        reversible_task_summaries = [
            self._build_task_summary(task) for task in reversible_page_obj.object_list
        ]
        context["tasks"] = pending_page_obj.object_list
        context["task_summaries"] = task_summaries
        context["reversible_tasks"] = reversible_page_obj.object_list
        context["reversible_task_summaries"] = reversible_task_summaries
        context["pending_page_obj"] = pending_page_obj
        context["reversible_page_obj"] = reversible_page_obj
        context["selected_task"] = selected_task
        context["selected_member_filter"] = member_filter
        context["stage_choices"] = PartyMemberStatus.Stage.choices
        context["current_filters"] = {
            "member": member_filter,
            "q": query,
            "stage": stage_filter,
            "sort": sort,
        }
        context["pending_page_query"] = self._build_query_string(exclude=["pending_page", "task"])
        context["reversible_page_query"] = self._build_query_string(
            exclude=["reversible_page", "task"]
        )
        context.setdefault(
            "decision_form",
            PartyApprovalDecisionForm(task=selected_task, operator=self.request.user),
        )
        context.setdefault(
            "batch_decision_form",
            PartyBatchApprovalForm(
                task_queryset=context["tasks"],
                operator=self.request.user,
            ),
        )
        context.setdefault("batch_selected_task_ids", [])
        context["selected_material_items"] = []
        if selected_task is not None:
            material_items, all_ready = workflow.get_material_status(selected_task.stage_instance)
            member = selected_task.stage_instance.member
            task_chain = self._get_task_chain(selected_task.stage_instance)
            latest_reject_action = None
            latest_processed_action = None
            all_actions = []
            for task_entry in task_chain:
                all_actions.extend(task_entry["actions"])
            for action in reversed(all_actions):
                if latest_processed_action is None and action.action in {"approve", "reject", "withdraw"}:
                    latest_processed_action = action
                if action.action == "reject" and action.comment:
                    latest_reject_action = action
                    break
            definitions = list(get_track_stage_definitions(member.track_type))
            completed_stage_count = member.stage_instances.filter(
                status=PartyStageInstance.Status.APPROVED
            ).count()
            context["selected_material_items"] = material_items
            context["selected_all_ready"] = all_ready
            context["selected_task_chain"] = task_chain
            context["selected_material_ready_count"] = sum(
                1 for item in material_items if item["submission"]
            )
            context["selected_material_total_count"] = len(material_items)
            context["selected_latest_submission"] = (
                selected_task.stage_instance.material_submissions.order_by("-submitted_at").first()
            )
            context["selected_track_label"] = (
                selected_task.stage_instance.member.get_track_type_display()
            )
            context["selected_stage_task_count"] = selected_task.stage_instance.approval_tasks.count()
            context["selected_latest_reject_action"] = latest_reject_action
            context["selected_latest_processed_action"] = latest_processed_action
            context["selected_member_context"] = {
                "grade": member.user.grade or "--",
                "major": member.user.major or "--",
                "pending_task_count": member.stage_instances.filter(
                    approval_tasks__status=PartyApprovalTask.Status.PENDING
                ).distinct().count(),
                "reversible_task_count": member.stage_instances.filter(
                    approval_tasks__status__in=[
                        PartyApprovalTask.Status.APPROVED,
                        PartyApprovalTask.Status.REJECTED,
                    ],
                    approval_tasks__can_withdraw_until__gte=workflow.timezone.now(),
                ).distinct().count(),
                "completed_stage_count": completed_stage_count,
                "total_stage_count": len(definitions),
                "current_node_name": selected_task.stage_instance.stage_definition.name,
            }
        else:
            context["selected_task_chain"] = []
            context["selected_material_ready_count"] = 0
            context["selected_material_total_count"] = 0
            context["selected_latest_submission"] = None
            context["selected_track_label"] = ""
            context["selected_stage_task_count"] = 0
            context["selected_latest_reject_action"] = None
            context["selected_latest_processed_action"] = None
            context["selected_member_context"] = {}
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("operation") == "withdraw":
            task = get_object_or_404(
                PartyApprovalTask.objects.select_related(
                    "stage_instance__member__user",
                    "stage_instance__stage_definition",
                ),
                pk=request.POST.get("task_id"),
                assignee_role=request.user.role,
            )
            try:
                approval.withdraw_task(
                    task,
                    request.user,
                    comment=request.POST.get("withdraw_comment", ""),
                )
            except ValidationError as exc:
                messages.error(request, exc.message)
                return redirect(f"{request.path}?task={task.pk}")
            messages.success(request, "审批结果已撤回，任务重新回到待审批。")
            return redirect(self._get_post_redirect_url(request))

        if request.POST.get("operation") == "batch_process":
            task_queryset = PartyApprovalTask.objects.select_related(
                "stage_instance__member__user",
                "stage_instance__stage_definition",
            ).filter(
                pk__in=request.POST.getlist("task_ids"),
                status=PartyApprovalTask.Status.PENDING,
                assignee_role=request.user.role,
            )
            form = PartyBatchApprovalForm(
                request.POST,
                task_queryset=task_queryset,
                operator=request.user,
            )
            if form.is_valid():
                action = form.cleaned_data["action"]
                comment = form.cleaned_data.get("comment", "")
                tasks = form.get_tasks()
                try:
                    approval.batch_process_tasks(
                        tasks,
                        request.user,
                        action=action,
                        comment=comment,
                    )
                except ValidationError as exc:
                    form.add_error(None, exc.message)
                else:
                    action_label = "批量通过" if action == PartyBatchApprovalForm.ACTION_APPROVE else "批量驳回"
                    messages.success(request, f"{action_label}已完成，共处理 {len(tasks)} 条任务。")
                    return redirect(self._get_post_redirect_url(request))
            return self.render_to_response(
                self.get_context_data(
                    batch_decision_form=form,
                    batch_selected_task_ids=request.POST.getlist("task_ids"),
                )
            )

        task = get_object_or_404(
            PartyApprovalTask.objects.select_related(
                "stage_instance__member__user",
                "stage_instance__stage_definition",
            ),
            pk=request.POST.get("task_id"),
            status=PartyApprovalTask.Status.PENDING,
            assignee_role=request.user.role,
        )
        form = PartyApprovalDecisionForm(
            request.POST,
            task=task,
            operator=request.user,
        )
        if form.is_valid():
            action = form.cleaned_data["action"]
            comment = form.cleaned_data.get("comment", "")
            try:
                if action == PartyApprovalDecisionForm.ACTION_APPROVE:
                    approval.approve_task(task, request.user, comment=comment)
                    messages.success(request, "审批已通过，流程已推进。")
                else:
                    approval.reject_task(task, request.user, comment=comment)
                    messages.success(request, "审批已驳回，学生可重新补交材料。")
            except ValidationError as exc:
                form.add_error(None, exc.message)
            else:
                return redirect(self._get_post_redirect_url(request))

        return self.render_to_response(
            self.get_context_data(
                decision_form=form,
                selected_task=task,
            )
        )


class AdminReminderOverviewView(AdminPartyMixin, TemplateView):
    template_name = "party/admin_reminders.html"
    back_url_name = "party:party_admin:dashboard"
    breadcrumb_items = (
        ("党团模块", "party:index"),
        ("管理端", "party:party_admin:dashboard"),
        ("提醒概览", None),
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reminder_queryset = PartyReminder.objects.select_related(
            "member__user",
            "stage_instance__stage_definition",
        ).order_by("status", "scheduled_at", "-created_at")
        context["pending_reminders"] = list(
            reminder_queryset.filter(status=PartyReminder.Status.PENDING)[:8]
        )
        context["sent_reminders"] = list(
            reminder_queryset.filter(status=PartyReminder.Status.SENT)[:8]
        )
        context["failed_reminders"] = list(
            reminder_queryset.filter(status=PartyReminder.Status.FAILED)[:8]
        )
        context["dashboard_counts"] = {
            "pending": PartyReminder.objects.filter(status=PartyReminder.Status.PENDING).count(),
            "sent": PartyReminder.objects.filter(status=PartyReminder.Status.SENT).count(),
            "failed": PartyReminder.objects.filter(status=PartyReminder.Status.FAILED).count(),
            "overdue_stage": PartyStageInstance.objects.filter(
                status__in=[
                    PartyStageInstance.Status.OPEN,
                    PartyStageInstance.Status.SUBMITTED,
                ],
                due_at__lt=workflow.timezone.now(),
            ).count(),
        }
        context["overdue_stage_instances"] = list(
            PartyStageInstance.objects.select_related(
                "member__user",
                "stage_definition",
            )
            .filter(
                status__in=[
                    PartyStageInstance.Status.OPEN,
                    PartyStageInstance.Status.SUBMITTED,
                ],
                due_at__lt=workflow.timezone.now(),
            )
            .order_by("due_at")[:8]
        )
        return context


class AdminRuleListView(AdminPartyMixin, TemplateView):
    template_name = "party/admin_rules.html"
    back_url_name = "party:party_admin:dashboard"
    breadcrumb_items = (
        ("党团模块", "party:index"),
        ("管理端", "party:party_admin:dashboard"),
        ("流程规则", None),
    )

    def _get_track_type(self):
        track_type = self.request.GET.get("track_type") or self.request.POST.get("track_type")
        valid_values = {value for value, _ in PartyMemberStatus.TrackType.choices}
        if track_type in valid_values:
            return track_type
        return PartyMemberStatus.TrackType.PARTY

    def _get_stage_queryset(self, track_type):
        return (
            PartyStageDefinition.objects.filter(track_type=track_type)
            .annotate(
                requirement_count=Count("material_requirements", distinct=True),
                instance_count=Count("instances", distinct=True),
            )
            .order_by("order", "id")
        )

    def _get_selected_stage(self, track_type):
        stage_queryset = self._get_stage_queryset(track_type)
        stage_id = self.request.GET.get("stage_id") or self.request.POST.get("current_stage_id")
        selected_stage = None
        if stage_id:
            selected_stage = stage_queryset.filter(pk=stage_id).first()
        return selected_stage or stage_queryset.first()

    def _build_rules_url(
        self,
        track_type,
        *,
        stage_id=None,
        stage_edit=None,
        material_edit=None,
        requirement_edit=None,
    ):
        params = {"track_type": track_type}
        if stage_id:
            params["stage_id"] = stage_id
        if stage_edit:
            params["stage_edit"] = stage_edit
        if material_edit:
            params["material_edit"] = material_edit
        if requirement_edit:
            params["requirement_edit"] = requirement_edit
        query = urlencode(params)
        url = reverse("party:party_admin:rules")
        return f"{url}?{query}" if query else url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        track_type = self._get_track_type()
        stage_definitions = list(
            self._get_stage_queryset(track_type).prefetch_related(
                "material_requirements__material_type"
            )
        )
        selected_stage = self._get_selected_stage(track_type)
        material_types = list(
            PartyMaterialType.objects.annotate(
                requirement_count=Count("stage_requirements", distinct=True),
            ).order_by("name")
        )
        requirements = []
        if selected_stage is not None:
            requirements = list(
                selected_stage.material_requirements.select_related("material_type").order_by(
                    "order",
                    "id",
                )
            )

        stage_edit_id = self.request.GET.get("stage_edit")
        material_edit_id = self.request.GET.get("material_edit")
        requirement_edit_id = self.request.GET.get("requirement_edit")

        stage_instance = None
        material_instance = None
        requirement_instance = None
        if stage_edit_id:
            stage_instance = PartyStageDefinition.objects.filter(pk=stage_edit_id).first()
        if material_edit_id:
            material_instance = PartyMaterialType.objects.filter(pk=material_edit_id).first()
        if requirement_edit_id:
            requirement_instance = PartyStageMaterialRequirement.objects.filter(
                pk=requirement_edit_id
            ).first()

        context.update(
            {
                "track_type": track_type,
                "track_choices": PartyMemberStatus.TrackType.choices,
                "stage_definitions": stage_definitions,
                "selected_stage": selected_stage,
                "material_types": material_types,
                "requirements": requirements,
                "stage_form": kwargs.get("stage_form")
                or PartyStageDefinitionForm(
                    instance=stage_instance,
                    initial={"track_type": track_type},
                ),
                "material_form": kwargs.get("material_form")
                or PartyMaterialTypeForm(instance=material_instance),
                "requirement_form": kwargs.get("requirement_form")
                or PartyStageMaterialRequirementForm(
                    instance=requirement_instance,
                    stage_definition=selected_stage,
                ),
                "stage_form_instance": stage_instance,
                "material_form_instance": material_instance,
                "requirement_form_instance": requirement_instance,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        operation = request.POST.get("operation")
        track_type = self._get_track_type()
        selected_stage = self._get_selected_stage(track_type)

        if operation == "save_stage":
            instance = None
            stage_id = request.POST.get("stage_id")
            if stage_id:
                instance = get_object_or_404(PartyStageDefinition, pk=stage_id)
            stage_form = PartyStageDefinitionForm(request.POST, instance=instance)
            if stage_form.is_valid():
                saved_stage = stage_form.save()
                workflow.log_party_action(
                    request.user,
                    "save party stage definition",
                    "PartyStageDefinition",
                    saved_stage.pk,
                    f"保存节点定义 {saved_stage.code}",
                )
                messages.success(request, "流程节点定义已保存。")
                return redirect(
                    self._build_rules_url(
                        saved_stage.track_type,
                        stage_id=saved_stage.pk,
                    )
                )
            return self.render_to_response(
                self.get_context_data(
                    stage_form=stage_form,
                )
            )

        if operation == "toggle_stage":
            stage = get_object_or_404(PartyStageDefinition, pk=request.POST.get("stage_id"))
            target_state = not stage.is_active
            if not target_state and stage.instances.exists():
                messages.error(request, "该节点已经存在流程实例，暂不允许直接停用。")
                return redirect(
                    self._build_rules_url(
                        stage.track_type,
                        stage_id=stage.pk,
                    )
                )
            stage.is_active = target_state
            stage.save(update_fields=["is_active"])
            workflow.log_party_action(
                request.user,
                "toggle party stage definition",
                "PartyStageDefinition",
                stage.pk,
                f"{'启用' if target_state else '停用'}节点定义 {stage.code}",
            )
            messages.success(
                request,
                f"节点定义已{'启用' if target_state else '停用'}。",
            )
            return redirect(
                self._build_rules_url(
                    stage.track_type,
                    stage_id=stage.pk,
                )
            )

        if operation == "save_material":
            instance = None
            material_id = request.POST.get("material_id")
            if material_id:
                instance = get_object_or_404(PartyMaterialType, pk=material_id)
            material_form = PartyMaterialTypeForm(request.POST, instance=instance)
            if material_form.is_valid():
                material = material_form.save()
                workflow.log_party_action(
                    request.user,
                    "save party material type",
                    "PartyMaterialType",
                    material.pk,
                    f"保存材料类型 {material.code}",
                )
                messages.success(request, "材料类型已保存。")
                return redirect(
                    self._build_rules_url(
                        track_type,
                        stage_id=selected_stage.pk if selected_stage else None,
                    )
                )
            return self.render_to_response(
                self.get_context_data(
                    material_form=material_form,
                )
            )

        if operation == "toggle_material":
            material = get_object_or_404(PartyMaterialType, pk=request.POST.get("material_id"))
            material.is_active = not material.is_active
            material.save(update_fields=["is_active"])
            workflow.log_party_action(
                request.user,
                "toggle party material type",
                "PartyMaterialType",
                material.pk,
                f"{'启用' if material.is_active else '停用'}材料类型 {material.code}",
            )
            messages.success(
                request,
                f"材料类型已{'启用' if material.is_active else '停用'}。",
            )
            return redirect(
                self._build_rules_url(
                    track_type,
                    stage_id=selected_stage.pk if selected_stage else None,
                )
            )

        if operation == "save_requirement":
            instance = None
            requirement_id = request.POST.get("requirement_id")
            if requirement_id:
                instance = get_object_or_404(PartyStageMaterialRequirement, pk=requirement_id)
            requirement_form = PartyStageMaterialRequirementForm(request.POST, instance=instance)
            if requirement_form.is_valid():
                requirement = requirement_form.save()
                workflow.log_party_action(
                    request.user,
                    "save party stage requirement",
                    "PartyStageMaterialRequirement",
                    requirement.pk,
                    f"保存节点材料要求 {requirement.stage_definition.code}:{requirement.material_type.code}",
                )
                messages.success(request, "节点材料要求已保存。")
                return redirect(
                    self._build_rules_url(
                        requirement.stage_definition.track_type,
                        stage_id=requirement.stage_definition_id,
                    )
                )
            return self.render_to_response(
                self.get_context_data(
                    requirement_form=requirement_form,
                )
            )

        if operation == "toggle_requirement_required":
            requirement = get_object_or_404(
                PartyStageMaterialRequirement,
                pk=request.POST.get("requirement_id"),
            )
            requirement.is_required = not requirement.is_required
            requirement.save(update_fields=["is_required"])
            workflow.log_party_action(
                request.user,
                "toggle party stage requirement required",
                "PartyStageMaterialRequirement",
                requirement.pk,
                f"{'设为必需' if requirement.is_required else '设为选填'} {requirement.material_type.code}",
            )
            messages.success(
                request,
                f"材料要求已切换为{'必需' if requirement.is_required else '选填'}。",
            )
            return redirect(
                self._build_rules_url(
                    requirement.stage_definition.track_type,
                    stage_id=requirement.stage_definition_id,
                )
            )

        messages.error(request, "无法识别的规则配置操作。")
        return redirect(
            self._build_rules_url(
                track_type,
                stage_id=selected_stage.pk if selected_stage else None,
            )
        )


class AdminImportExportView(AdminPartyMixin, TemplateView):
    template_name = "party/admin_import.html"
    session_error_key = "party_import_errors"
    session_preview_key = "party_import_preview_rows"
    back_url_name = "party:party_admin:dashboard"
    breadcrumb_items = (
        ("党团模块", "party:index"),
        ("管理端", "party:party_admin:dashboard"),
        ("导入导出", None),
    )

    def get(self, request, *args, **kwargs):
        action = request.GET.get("action")
        if action == "download_template":
            return import_export.build_import_template_response()
        if action == "export_members":
            return import_export.build_member_export_response()
        if action == "export_approvals":
            return import_export.build_approval_export_response()
        if action == "download_errors":
            error_rows = request.session.get(self.session_error_key) or []
            if not error_rows:
                messages.error(request, "当前没有可下载的导入错误清单。")
                return redirect("party:party_admin:import_export")
            return import_export.build_import_error_response(error_rows)
        if action == "clear_preview":
            request.session.pop(self.session_preview_key, None)
            request.session.modified = True
            messages.success(request, "已取消本次导入预览。")
            return redirect("party:party_admin:import_export")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["import_form"] = kwargs.get("import_form") or PartyImportWorkbookForm()
        context["import_error_rows"] = self.request.session.get(self.session_error_key) or []
        context["import_preview_rows"] = self.request.session.get(self.session_preview_key) or []
        return context

    def post(self, request, *args, **kwargs):
        operation = request.POST.get("operation") or "preview_import"
        if operation == "confirm_import":
            preview_rows = request.session.get(self.session_preview_key) or []
            if not preview_rows:
                messages.error(request, "没有可确认的导入预览，请先上传 Excel 进行预校验。")
                return redirect("party:party_admin:import_export")
            imported_count = import_export.import_member_preview_rows(
                preview_rows,
                operator=request.user,
            )
            request.session.pop(self.session_preview_key, None)
            request.session.pop(self.session_error_key, None)
            workflow.log_party_action(
                request.user,
                "import party member workbook",
                "PartyMemberStatus",
                "",
                f"批量导入 {imported_count} 条党团流程记录",
            )
            messages.success(request, f"Excel 导入完成，共处理 {imported_count} 条记录。")
            return redirect("party:party_admin:import_export")

        form = PartyImportWorkbookForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                preview_rows = import_export.preview_member_workbook(
                    form.cleaned_data["file"],
                )
            except import_export.PartyImportValidationError as exc:
                request.session.pop(self.session_preview_key, None)
                request.session[self.session_error_key] = exc.error_rows
                request.session.modified = True
                messages.error(
                    request,
                    f"导入失败，共发现 {len(exc.error_rows)} 行错误。请先下载错误清单修正后再导入。",
                )
            except ValidationError as exc:
                if hasattr(exc, "messages"):
                    for message in exc.messages:
                        messages.error(request, message)
                else:
                    messages.error(request, str(exc))
            else:
                request.session.pop(self.session_error_key, None)
                request.session[self.session_preview_key] = preview_rows
                request.session.modified = True
                messages.success(
                    request,
                    f"预校验通过，共识别 {len(preview_rows)} 条记录。请确认预览后再正式导入。",
                )
                return redirect("party:party_admin:import_export")
        return self.render_to_response(self.get_context_data(import_form=form))
