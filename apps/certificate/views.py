from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.http import FileResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import CertificateLog, CertificateMaterial, CertificateRequest


CERTIFICATE_OPTIONS = {
    "party-member": {
        "icon": "🏛️",
        "name": "党员身份证明",
        "description": "用于政审、组织关系核验等正式场景。",
        "tag": "高频使用",
        "preview_title": "中共党员身份证明",
    },
    "study-status": {
        "icon": "📘",
        "name": "在读证明",
        "description": "用于竞赛报名、社会实践和单位材料提交。",
        "tag": "常规证明",
        "preview_title": "在读证明",
    },
    "identity": {
        "icon": "🧾",
        "name": "学籍身份说明",
        "description": "用于身份核验、信息补充和临时材料说明。",
        "tag": "补充说明",
        "preview_title": "学籍身份说明",
    },
}

STATUS_META = {
    CertificateRequest.STATUS_DRAFT: {
        "label": "待提交",
        "pill_class": "pill-primary",
        "student_summary": "申请尚未正式提交，请完成填写后提交。",
    },
    CertificateRequest.STATUS_MATERIAL_PENDING: {
        "label": "待材料校验",
        "pill_class": "pill-warning",
        "student_summary": "系统正在进行材料完整性校验。",
    },
    CertificateRequest.STATUS_MATERIAL_REJECTED: {
        "label": "待补充材料",
        "pill_class": "pill-warning",
        "student_summary": "材料完整性校验未通过，请补充后重新提交。",
    },
    CertificateRequest.STATUS_PENDING_REVIEW: {
        "label": "审核中",
        "pill_class": "pill-warning",
        "student_summary": "申请已提交，当前正在等待管理员审核。",
    },
    CertificateRequest.STATUS_REJECTED: {
        "label": "退回修改",
        "pill_class": "pill-warning",
        "student_summary": "申请已被退回，请根据意见修改后重新提交。",
    },
    CertificateRequest.STATUS_APPROVED_OBSERVING: {
        "label": "已签发（观察期内）",
        "pill_class": "pill-primary",
        "student_summary": "预览稿已生成，当前处于 24 小时撤回观察期，办结后才能下载正式文件。",
    },
    CertificateRequest.STATUS_REVOKED: {
        "label": "已撤回",
        "pill_class": "pill-warning",
        "student_summary": "该申请已撤回，原文件已作废。",
    },
    CertificateRequest.STATUS_COMPLETED: {
        "label": "已办结",
        "pill_class": "pill-success",
        "student_summary": "该申请已正式办结，可继续下载留存。",
    },
}

MATERIAL_DEFINITIONS = [
    ("用途说明", "请简要说明证明使用场景，例如政审、比赛报名或材料补充。", True),
    ("相关附件", "如需辅助核验，可补充通知截图、接收单位要求等材料。", True),
    ("关键字段校验", "系统将核对学号、专业、身份信息及开证明所需关键字段。", True),
]


PDF_FONT_NAME = "Helvetica"


def register_pdf_font():
    global PDF_FONT_NAME
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for font_path in candidates:
        try:
            pdfmetrics.registerFont(TTFont("CertificateChinese", font_path))
            PDF_FONT_NAME = "CertificateChinese"
            return
        except Exception:
            continue



def build_reference_no():
    today = timezone.localtime().strftime("%Y%m%d")
    count = CertificateRequest.objects.filter(reference_no__startswith=f"CERT-{today}").count() + 1
    return f"CERT-{today}-{count:04d}"


def add_log(request_obj, action, detail, operator):
    CertificateLog.objects.create(
        request=request_obj,
        action=action,
        detail=detail,
        operator=operator,
    )


def create_materials(request_obj, attachment_note):
    request_obj.materials.all().delete()
    for index, (name, detail, is_required) in enumerate(MATERIAL_DEFINITIONS):
        is_valid = True
        if index == 1:
            is_valid = bool(attachment_note.strip())
        CertificateMaterial.objects.create(
            request=request_obj,
            name=name,
            detail=detail,
            is_required=is_required,
            is_valid=is_valid,
        )


def material_check_passed(request_obj):
    return request_obj.materials.filter(is_required=True, is_valid=False).count() == 0


def build_certificate_pdf(request_obj, student, is_preview=False):
    register_pdf_font()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=24 * mm,
        leftMargin=24 * mm,
        topMargin=26 * mm,
        bottomMargin=24 * mm,
        title=request_obj.cert_type,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CertificateTitle",
        parent=styles["Title"],
        fontName=PDF_FONT_NAME,
        fontSize=22,
        leading=30,
        textColor=colors.HexColor("#A6192E"),
        alignment=TA_CENTER,
        spaceAfter=18,
    )
    body_style = ParagraphStyle(
        "CertificateBody",
        parent=styles["BodyText"],
        fontName=PDF_FONT_NAME,
        fontSize=12,
        leading=22,
        alignment=TA_LEFT,
        spaceAfter=10,
    )
    small_style = ParagraphStyle(
        "CertificateSmall",
        parent=body_style,
        fontSize=10,
        leading=16,
        textColor=colors.HexColor("#6B7280"),
    )
    stamp_style = ParagraphStyle(
        "CertificateStamp",
        parent=body_style,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#A6192E"),
        alignment=TA_CENTER,
    )
    profile = get_student_profile(student)
    issued_at = timezone.localtime().strftime("%Y-%m-%d")
    verify_code = f"{request_obj.reference_no}-ISE"
    document_state = "预览稿" if is_preview else "正式文件"

    table_data = [
        ["姓名", profile["name"], "学号", profile["student_id"]],
        ["性别", profile["gender"], "专业", profile["major"]],
        ["申请单号", request_obj.reference_no, "文件状态", document_state],
    ]
    table = Table(table_data, colWidths=[26 * mm, 54 * mm, 26 * mm, 54 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), PDF_FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7F7")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2F2F2F")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5C7C7")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    story = [
        Paragraph("学院学生事务服务中心", small_style),
        Paragraph(request_obj.cert_type, title_style),
        table,
        Spacer(1, 14),
        Paragraph(
            f"兹证明：{profile['name']}，学号 {profile['student_id']}，性别 {profile['gender']}，"
            f"现就读于 {profile['major']} 专业。",
            body_style,
        ),
        Paragraph(f"本证明用途：{request_obj.purpose or '未填写'}。", body_style),
        Paragraph(
            "本文件由线上证明系统依据学生基础信息和申请材料生成。"
            "预览稿仅用于提交前或观察期内核对内容，不作为正式下载文件使用。"
            if is_preview
            else "本文件已完成线上申请、材料校验、审批及观察期流程，可作为正式证明文件下载留存。",
            body_style,
        ),
        Spacer(1, 18),
        Paragraph("学院学生事务服务中心", stamp_style),
        Paragraph(f"签发日期：{issued_at}", body_style),
        Spacer(1, 8),
        Paragraph(f"防伪校验码：{verify_code}", small_style),
    ]
    if is_preview:
        story.append(Paragraph("文件标记：预览稿，仅供核对，不可作为正式证明使用。", small_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_demo_file(request_obj, student):
    pdf_bytes = build_certificate_pdf(request_obj, student, is_preview=False)
    filename = f"{request_obj.reference_no}.pdf"
    request_obj.generated_pdf.save(filename, ContentFile(pdf_bytes), save=False)
    request_obj.is_pdf_void = False


def build_draft_preview_request(selected_type, purpose):
    cert_info = CERTIFICATE_OPTIONS.get(selected_type, CERTIFICATE_OPTIONS["party-member"])
    return SimpleNamespace(
        reference_no=f"PREVIEW-{timezone.localtime().strftime('%Y%m%d%H%M%S')}",
        cert_type=cert_info["name"],
        purpose=purpose,
    )


def pdf_response(pdf_bytes, filename, as_attachment=False):
    return FileResponse(
        BytesIO(pdf_bytes),
        content_type="application/pdf",
        filename=filename,
        as_attachment=as_attachment,
    )


def sync_completed_if_expired(request_obj):
    if (
        request_obj.status == CertificateRequest.STATUS_APPROVED_OBSERVING
        and request_obj.revoke_deadline
        and request_obj.revoke_deadline <= timezone.now()
    ):
        request_obj.status = CertificateRequest.STATUS_COMPLETED
        request_obj.completed_at = timezone.now()
        request_obj.last_operator = "系统"
        request_obj.save(update_fields=["status", "completed_at", "last_operator", "updated_at"])
        add_log(request_obj, "观察期结束", "24小时内未撤回，流程自动办结。", "系统")


def sync_all_requests(student):
    for request_obj in CertificateRequest.objects.filter(applicant=student):
        sync_completed_if_expired(request_obj)

def sync_all_requests_for_queryset(queryset):
    for request_obj in queryset:
        sync_completed_if_expired(request_obj)


def option_id_from_name(cert_name):
    for key, value in CERTIFICATE_OPTIONS.items():
        if value["name"] == cert_name:
            return key
    return "party-member"


def get_student_profile(student):
    gender = "未填写"
    if student.id_number and len(student.id_number) == 18:
        # 从身份证号提取性别（倒数第二位，奇数为男，偶数为女）
        try:
            gender_digit = int(student.id_number[-2])
            gender = "男" if gender_digit % 2 == 1 else "女"
        except (ValueError, IndexError):
            gender = "未填写"

    return {
        "name": student.real_name or student.username,
        "student_id": student.student_id or "未填写",
        "major": student.major or "未填写",
        "gender": gender,
    }


def get_status_payload(request_obj):
    meta = STATUS_META[request_obj.status]
    window = "--"
    if request_obj.status == CertificateRequest.STATUS_APPROVED_OBSERVING and request_obj.revoke_deadline:
        remaining = request_obj.revoke_deadline - timezone.now()
        if remaining.total_seconds() > 0:
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            window = f"剩余 {hours}小时{minutes}分"
        else:
            window = "观察期已结束"
    elif request_obj.status == CertificateRequest.STATUS_COMPLETED:
        window = "观察期已结束"
    elif request_obj.status == CertificateRequest.STATUS_REVOKED:
        window = "已撤回"

    pdf_state = "未生成"
    if request_obj.generated_pdf:
        pdf_state = "已作废" if request_obj.is_pdf_void else "预览稿已生成"
        if request_obj.status == CertificateRequest.STATUS_COMPLETED:
            pdf_state = "正式文件已生成"

    can_preview = bool(request_obj.generated_pdf and not request_obj.is_pdf_void)
    can_download = bool(
        request_obj.generated_pdf
        and not request_obj.is_pdf_void
        and request_obj.status == CertificateRequest.STATUS_COMPLETED
    )
    can_revoke = request_obj.status == CertificateRequest.STATUS_APPROVED_OBSERVING
    can_resubmit = request_obj.status in {
        CertificateRequest.STATUS_MATERIAL_REJECTED,
        CertificateRequest.STATUS_REJECTED,
        CertificateRequest.STATUS_REVOKED,
    }

    return {
        "certificate_name": request_obj.cert_type,
        "status_key": request_obj.status,
        "status": meta["label"],
        "status_class": meta["pill_class"],
        "summary": meta["student_summary"],
        "reference": request_obj.reference_no,
        "created_at": timezone.localtime(request_obj.created_at).strftime("%Y-%m-%d %H:%M"),
        "updated_at": timezone.localtime(request_obj.updated_at).strftime("%Y-%m-%d %H:%M"),
        "window": window,
        "pdf_state": pdf_state,
        "can_preview": can_preview,
        "can_download": can_download,
        "can_revoke": can_revoke,
        "can_resubmit": can_resubmit,
    }


def build_timeline(request_obj):
    status = request_obj.status
    return [
        {
            "title": "学生提交申请",
            "detail": "选择证明类型，核对个人信息并提交申请。",
            "state": "done" if status != CertificateRequest.STATUS_DRAFT else "current",
        },
        {
            "title": "材料完整性校验",
            "detail": "若材料不完整，系统提示补充材料并重新提交。",
            "state": (
                "done"
                if status in {
                    CertificateRequest.STATUS_PENDING_REVIEW,
                    CertificateRequest.STATUS_REJECTED,
                    CertificateRequest.STATUS_APPROVED_OBSERVING,
                    CertificateRequest.STATUS_REVOKED,
                    CertificateRequest.STATUS_COMPLETED,
                }
                else "current" if status in {
                    CertificateRequest.STATUS_MATERIAL_PENDING,
                    CertificateRequest.STATUS_MATERIAL_REJECTED,
                } else "upcoming"
            ),
        },
        {
            "title": "管理员审批",
            "detail": "通过后生成文件，退回后可修改并重新提交。",
            "state": (
                "done"
                if status in {
                    CertificateRequest.STATUS_REJECTED,
                    CertificateRequest.STATUS_APPROVED_OBSERVING,
                    CertificateRequest.STATUS_REVOKED,
                    CertificateRequest.STATUS_COMPLETED,
                }
                else "current" if status == CertificateRequest.STATUS_PENDING_REVIEW else "upcoming"
            ),
        },
        {
            "title": "文件生成与观察期",
            "detail": "生成文件后进入 24 小时观察期，可在观察期内撤回。",
            "state": (
                "done"
                if status in {
                    CertificateRequest.STATUS_REVOKED,
                    CertificateRequest.STATUS_COMPLETED,
                }
                else "current" if status == CertificateRequest.STATUS_APPROVED_OBSERVING else "upcoming"
            ),
        },
        {
            "title": "最终办结",
            "detail": "观察期结束后正式办结，证明长期可下载。",
            "state": "done" if status == CertificateRequest.STATUS_COMPLETED else "upcoming",
        },
    ]


def build_request_rows(student):
    sync_all_requests(student)
    rows = []
    queryset = CertificateRequest.objects.filter(applicant=student).order_by("-created_at", "-id")
    for item in queryset:
        status_payload = get_status_payload(item)
        rows.append(
            {
                "id": item.id,
                "reference": item.reference_no,
                "cert_type": item.cert_type,
                "status": status_payload["status"],
                "status_class": status_payload["status_class"],
                "created_at": timezone.localtime(item.created_at).strftime("%Y-%m-%d %H:%M"),
                "updated_at": timezone.localtime(item.updated_at).strftime("%Y-%m-%d %H:%M"),
                "pdf_state": status_payload["pdf_state"],
                "can_preview": status_payload["can_preview"],
                "can_download": status_payload["can_download"],
                "can_revoke": status_payload["can_revoke"],
                "can_resubmit": status_payload["can_resubmit"],
            }
        )
    return rows


def get_request_or_404(user, pk):
    if user.is_authenticated and user.is_admin_or_above():
        request_obj = get_object_or_404(CertificateRequest, pk=pk)
    else:
        request_obj = get_object_or_404(CertificateRequest, pk=pk, applicant=user)
    sync_completed_if_expired(request_obj)
    request_obj.refresh_from_db()
    return request_obj


def create_request(student, selected_type, purpose, attachment_note):
    cert_info = CERTIFICATE_OPTIONS.get(selected_type, CERTIFICATE_OPTIONS["party-member"])
    request_obj = CertificateRequest.objects.create(
        applicant=student,
        reference_no=build_reference_no(),
        cert_type=cert_info["name"],
        purpose=purpose,
        attachment_note=attachment_note,
        status=CertificateRequest.STATUS_MATERIAL_PENDING,
        submitted_at=timezone.now(),
        last_operator="学生提交",
    )
    create_materials(request_obj, attachment_note)
    add_log(request_obj, "提交申请单", f"学生提交 {request_obj.cert_type} 申请。", "学生")

    if not purpose or not attachment_note or not material_check_passed(request_obj):
        request_obj.status = CertificateRequest.STATUS_MATERIAL_REJECTED
        request_obj.rejection_reason = "材料完整性校验未通过：请补充用途说明和相关附件说明后重新提交。"
        request_obj.last_operator = "系统校验"
        request_obj.save(update_fields=["status", "rejection_reason", "last_operator", "updated_at"])
        add_log(
            request_obj,
            "材料校验未通过",
            "系统提示补充材料，流程返回学生端重新提交。",
            "系统",
        )
        return request_obj, False

    request_obj.status = CertificateRequest.STATUS_PENDING_REVIEW
    request_obj.last_operator = "系统校验"
    request_obj.save(update_fields=["status", "last_operator", "updated_at"])
    add_log(request_obj, "材料校验通过", "申请已流转至管理员处理环节。", "系统")
    return request_obj, True


def update_request_for_resubmit(request_obj, selected_type, purpose, attachment_note):
    cert_info = CERTIFICATE_OPTIONS.get(selected_type, CERTIFICATE_OPTIONS["party-member"])
    request_obj.cert_type = cert_info["name"]
    request_obj.purpose = purpose
    request_obj.attachment_note = attachment_note
    request_obj.submitted_at = timezone.now()
    request_obj.rejection_reason = ""
    request_obj.is_pdf_void = False
    request_obj.revoked_at = None
    request_obj.completed_at = None
    request_obj.revoke_deadline = None
    request_obj.approved_at = None
    request_obj.last_operator = "学生重新提交"
    request_obj.save()
    create_materials(request_obj, attachment_note)
    add_log(request_obj, "重新提交申请", f"学生重新提交 {request_obj.cert_type} 申请。", "学生")

    if not purpose or not attachment_note or not material_check_passed(request_obj):
        request_obj.status = CertificateRequest.STATUS_MATERIAL_REJECTED
        request_obj.rejection_reason = "材料完整性校验未通过：请补充用途说明和相关附件说明后重新提交。"
        request_obj.last_operator = "系统校验"
        request_obj.save(update_fields=["status", "rejection_reason", "last_operator", "updated_at"])
        add_log(
            request_obj,
            "材料校验未通过",
            "系统提示补充材料，流程返回学生端重新提交。",
            "系统",
        )
        return False

    request_obj.status = CertificateRequest.STATUS_PENDING_REVIEW
    request_obj.last_operator = "系统校验"
    request_obj.save(update_fields=["status", "last_operator", "updated_at"])
    add_log(request_obj, "材料校验通过", "申请已再次流转至管理员处理环节。", "系统")
    return True


class ListView(LoginRequiredMixin, TemplateView):
    template_name = "certificate/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # If admin/leader, show all requests. Else show only their own.
        if user.is_admin_or_above():
            sync_all_requests_for_queryset(CertificateRequest.objects.all())
            queryset = CertificateRequest.objects.all().order_by("-created_at", "-id")
        else:
            sync_all_requests(user)
            queryset = CertificateRequest.objects.filter(applicant=user).order_by("-created_at", "-id")
            
        rows = []
        for item in queryset:
            status_payload = get_status_payload(item)
            rows.append(
                {
                    "id": item.id,
                    "reference": item.reference_no,
                    "cert_type": item.cert_type,
                    "status": status_payload["status"],
                    "status_class": status_payload["status_class"],
                    "created_at": timezone.localtime(item.created_at).strftime("%Y-%m-%d %H:%M"),
                    "updated_at": timezone.localtime(item.updated_at).strftime("%Y-%m-%d %H:%M"),
                    "pdf_state": status_payload["pdf_state"],
                    "can_preview": status_payload["can_preview"],
                    "can_download": status_payload["can_download"],
                    "can_revoke": status_payload["can_revoke"],
                    "can_resubmit": status_payload["can_resubmit"],
                    "applicant_name": item.applicant.real_name or item.applicant.username,
                }
            )
            
        context["page_intro"] = "按时间查看历史申请，点击某一条即可进入详情查看状态、下载文件或撤回。"
        context["student_profile"] = get_student_profile(user)
        context["request_rows"] = rows
        context["is_admin"] = user.is_admin_or_above()
        return context


class CreateView(LoginRequiredMixin, TemplateView):
    template_name = "certificate/create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["page_intro"] = "新建证明申请时先确认个人信息，再填写用途说明、附件说明并提交。"
        context["student_profile"] = get_student_profile(user)
        context["certificate_types"] = [{"id": key, **value} for key, value in CERTIFICATE_OPTIONS.items()]
        context["selected_certificate_type"] = self.request.GET.get("type", "party-member")
        context["form_values"] = {
            "purpose": self.request.GET.get("purpose", ""),
            "attachment_note": self.request.GET.get("attachment_note", ""),
        }
        context["materials"] = [
            {"name": name, "detail": detail, "status": "待填写", "pill_class": "pill-warning"}
            for name, detail, _ in MATERIAL_DEFINITIONS
        ]
        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        selected_type = request.POST.get("certificate_type", "party-member")
        purpose = request.POST.get("purpose", "").strip()
        attachment_note = request.POST.get("attachment_note", "").strip()
        request_obj, success = create_request(user, selected_type, purpose, attachment_note)
        if success:
            messages.success(request, "申请已提交，当前等待管理员审核。")
        else:
            messages.warning(request, "材料完整性校验未通过，请先在详情页补充后重新提交。")
        return redirect("certificate:detail", pk=request_obj.pk)


class DetailView(LoginRequiredMixin, TemplateView):
    template_name = "certificate/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        request_obj = get_request_or_404(user, kwargs["pk"])

        context["student_profile"] = get_student_profile(request_obj.applicant)
        context["request_obj"] = request_obj
        context["active_application"] = get_status_payload(request_obj)
        context["selected_certificate_type"] = option_id_from_name(request_obj.cert_type)
        context["certificate_types"] = [{"id": key, **value} for key, value in CERTIFICATE_OPTIONS.items()]
        context["materials"] = [
            {
                "name": item.name,
                "detail": item.detail,
                "status": "校验通过" if item.is_valid else "待补充",
                "pill_class": "pill-success" if item.is_valid else "pill-warning",
            }
            for item in request_obj.materials.all()
        ]
        context["timeline_steps"] = build_timeline(request_obj)
        context["application_history"] = [
            {
                "time": timezone.localtime(item.created_at).strftime("%Y-%m-%d %H:%M"),
                "title": item.action,
                "detail": item.detail,
            }
            for item in request_obj.logs.order_by("-created_at")
        ]
        context["rejection_note"] = {
            "exists": bool(request_obj.rejection_reason),
            "time": timezone.localtime(request_obj.updated_at).strftime("%Y-%m-%d %H:%M"),
            "content": request_obj.rejection_reason,
        }
        context["form_values"] = {
            "purpose": request_obj.purpose,
            "attachment_note": request_obj.attachment_note,
        }
        context["download_url"] = reverse("certificate:download", args=[request_obj.id])
        context["preview_url"] = reverse("certificate:preview", args=[request_obj.id])
        context["resubmit_url"] = reverse("certificate:resubmit", args=[request_obj.id])
        context["revoke_url"] = reverse("certificate:revoke", args=[request_obj.id])
        return context


class ResubmitView(LoginRequiredMixin, View):
    def post(self, request, pk):
        user = request.user
        request_obj = get_request_or_404(user, pk)

        if request_obj.status not in {
            CertificateRequest.STATUS_MATERIAL_REJECTED,
            CertificateRequest.STATUS_REJECTED,
            CertificateRequest.STATUS_REVOKED,
        }:
            messages.warning(request, "当前状态下不能重新提交。")
            return redirect("certificate:detail", pk=pk)

        selected_type = request.POST.get("certificate_type", "party-member")
        purpose = request.POST.get("purpose", "").strip()
        attachment_note = request.POST.get("attachment_note", "").strip()
        success = update_request_for_resubmit(request_obj, selected_type, purpose, attachment_note)

        if success:
            messages.success(request, "申请已重新提交，当前等待管理员审核。")
        else:
            messages.warning(request, "材料完整性校验未通过，请继续补充后再次提交。")
        return redirect("certificate:detail", pk=pk)


class RevokeView(LoginRequiredMixin, View):
    def post(self, request, pk):
        user = request.user
        request_obj = get_request_or_404(user, pk)
        if request_obj.status != CertificateRequest.STATUS_APPROVED_OBSERVING:
            messages.warning(request, "当前状态下不能撤回。")
            return redirect("certificate:detail", pk=pk)

        request_obj.status = CertificateRequest.STATUS_REVOKED
        request_obj.revoked_at = timezone.now()
        request_obj.is_pdf_void = True
        request_obj.last_operator = "学生撤回"
        request_obj.save(update_fields=["status", "revoked_at", "is_pdf_void", "last_operator", "updated_at"])
        add_log(request_obj, "学生撤回", "学生在观察期内主动撤回申请，原文件作废。", "学生")
        messages.success(request, "申请已撤回，原文件已作废。")
        return redirect("certificate:detail", pk=pk)


class DownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        user = request.user
        request_obj = get_request_or_404(user, pk)
        if request_obj.status != CertificateRequest.STATUS_COMPLETED:
            messages.warning(request, "申请尚未全流程办结，只能查看预览稿，暂不能下载正式文件。")
            return HttpResponseRedirect(reverse("certificate:detail", args=[pk]))
        if request_obj.is_pdf_void:
            messages.warning(request, "该文件已作废，不能下载。")
            return HttpResponseRedirect(reverse("certificate:detail", args=[pk]))
        if not request_obj.generated_pdf or not request_obj.generated_pdf.name.lower().endswith(".pdf"):
            generate_demo_file(request_obj, request_obj.applicant)
            request_obj.save(update_fields=["generated_pdf", "is_pdf_void", "updated_at"])
        return redirect(request_obj.generated_pdf.url)


class PreviewDraftView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        selected_type = request.GET.get("certificate_type", "party-member")
        purpose = request.GET.get("purpose", "").strip() or "预览用途，正式提交时以填写内容为准"
        draft_request = build_draft_preview_request(selected_type, purpose)
        pdf_bytes = build_certificate_pdf(draft_request, user, is_preview=True)
        return pdf_response(pdf_bytes, f"{draft_request.reference_no}.pdf")


class PreviewView(LoginRequiredMixin, View):
    def get(self, request, pk):
        user = request.user
        request_obj = get_request_or_404(user, pk)
        if request_obj.is_pdf_void:
            messages.warning(request, "该文件已作废，不能预览。")
            return HttpResponseRedirect(reverse("certificate:detail", args=[pk]))
        pdf_bytes = build_certificate_pdf(request_obj, request_obj.applicant, is_preview=True)
        return pdf_response(pdf_bytes, f"{request_obj.reference_no}-preview.pdf")
