import os
from io import BytesIO

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from ninja import Router, Schema
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.pdfgen import canvas

from apps.certificate.models import CertificateRequest
from apps.users.models import User
from utils.response import error, success


CERTIFICATE_TYPE_CHOICES = [
    '在读证明',
    '党员发展情况证明',
    '获奖情况证明',
]

DEMO_USER_PRESETS = {
    'student': {
        'username': 'cert_demo_student',
        'real_name': '张三同学',
        'student_id': '2023101001',
        'grade': '2023级',
        'major': '信息系统工程',
        'email': 'student@example.com',
        'id_number': '110101200501011234',
        'role': User.ROLE_STUDENT,
    },
    'cadre': {
        'username': 'cert_demo_cadre',
        'real_name': '李老师',
        'student_id': None,
        'grade': '',
        'major': '学生工作办公室',
        'email': 'cadre@example.com',
        'id_number': '',
        'role': User.ROLE_CADRE,
    },
    'admin': {
        'username': 'cert_demo_admin',
        'real_name': '王老师',
        'student_id': None,
        'grade': '',
        'major': '学院党委',
        'email': 'admin@example.com',
        'id_number': '',
        'role': User.ROLE_ADMIN,
    },
}

router = Router()


class CertificateApplyIn(Schema):
    cert_type: str
    purpose: str


class CertificateReviewIn(Schema):
    action: str


def _get_display_name(user):
    return user.real_name or user.username


def _build_unique_demo_student_id(base_value):
    base_text = (base_value or 'DEMO').replace(' ', '')
    base_text = base_text[:12]
    for index in range(1, 100):
        candidate = f'{base_text}D{index:02d}'
        if not User.objects.filter(student_id=candidate).exists():
            return candidate
    return None


def _get_demo_user(request):
    role_key = request.session.get('certificate_demo_role', 'student')
    preset = DEMO_USER_PRESETS.get(role_key, DEMO_USER_PRESETS['student'])
    user = User.objects.filter(username=preset['username']).first()
    if user:
        fields_to_update = []
        for field, value in preset.items():
            if field == 'username':
                continue
            if field == 'student_id' and value and User.objects.exclude(pk=user.pk).filter(student_id=value).exists():
                value = user.student_id or _build_unique_demo_student_id(value)
            if getattr(user, field) != value:
                setattr(user, field, value)
                fields_to_update.append(field)
        if fields_to_update:
            user.save(update_fields=fields_to_update)
        return role_key, user

    defaults = preset.copy()
    student_id = defaults.get('student_id')
    if student_id and User.objects.filter(student_id=student_id).exists():
        defaults['student_id'] = _build_unique_demo_student_id(student_id)

    user = User.objects.create(**defaults)
    user.set_unusable_password()
    user.save(update_fields=['password'])
    return role_key, user


def _mask_id_number(id_number):
    if len(id_number) < 8:
        return id_number or '未登记'
    return f'{id_number[:4]}********{id_number[-4:]}'


def _serialize_user(user):
    return {
        'id': user.id,
        'username': user.username,
        'real_name': _get_display_name(user),
        'student_id': user.student_id or '',
        'role': user.role,
        'grade': user.grade or '',
        'major': user.major or '',
    }


def _serialize_request(cert_request):
    return {
        'id': cert_request.id,
        'cert_type': cert_request.cert_type,
        'purpose': cert_request.purpose,
        'status': cert_request.status,
        'status_display': cert_request.get_status_display(),
        'applicant': _serialize_user(cert_request.applicant),
        'first_reviewer': (
            _serialize_user(cert_request.first_reviewer) if cert_request.first_reviewer else None
        ),
        'final_reviewer': (
            _serialize_user(cert_request.final_reviewer) if cert_request.final_reviewer else None
        ),
        'created_at': timezone.localtime(cert_request.created_at).strftime('%Y-%m-%d %H:%M'),
        'reviewed_at': (
            timezone.localtime(cert_request.reviewed_at).strftime('%Y-%m-%d %H:%M')
            if cert_request.reviewed_at
            else None
        ),
        'generated_pdf': cert_request.generated_pdf.url if cert_request.generated_pdf else '',
    }


def _get_dashboard_context(user):
    my_requests = CertificateRequest.objects.filter(applicant=user).select_related(
        'applicant', 'first_reviewer', 'final_reviewer'
    )
    first_review_queue = CertificateRequest.objects.filter(
        status=CertificateRequest.STATUS_PENDING
    ).select_related('applicant')
    final_review_queue = CertificateRequest.objects.filter(
        status=CertificateRequest.STATUS_FIRST_REVIEW
    ).select_related('applicant', 'first_reviewer')
    return {
        'my_requests': my_requests,
        'first_review_queue': first_review_queue,
        'final_review_queue': final_review_queue,
    }


def _create_certificate_request(current_user, cert_type, purpose):
    if current_user.role != User.ROLE_STUDENT:
        raise PermissionDenied('当前演示身份不能提交证明申请。')
    if cert_type not in CERTIFICATE_TYPE_CHOICES:
        raise ValueError('请选择有效的证明类型。')
    if not purpose:
        raise ValueError('请填写申请用途。')

    return CertificateRequest.objects.create(
        applicant=current_user,
        cert_type=cert_type,
        purpose=purpose,
    )


def _review_certificate_request(current_user, cert_request, action):
    now = timezone.now()
    if cert_request.status == CertificateRequest.STATUS_PENDING and current_user.role == User.ROLE_CADRE:
        cert_request.first_reviewer = current_user
        cert_request.reviewed_at = now
        if action == 'approve':
            cert_request.status = CertificateRequest.STATUS_FIRST_REVIEW
            message = '初审已通过，申请已流转至终审。'
        elif action == 'reject':
            cert_request.status = CertificateRequest.STATUS_REJECTED
            message = '申请已在初审环节驳回。'
        else:
            raise ValueError('无效的审批动作。')
        cert_request.save()
        return message

    if cert_request.status == CertificateRequest.STATUS_FIRST_REVIEW and current_user.role in (
        User.ROLE_ADMIN,
        User.ROLE_LEADER,
    ):
        cert_request.final_reviewer = current_user
        cert_request.reviewed_at = now
        if action == 'approve':
            cert_request.status = CertificateRequest.STATUS_APPROVED
            _build_certificate_pdf(cert_request)
            message = '终审已通过，系统已自动生成 PDF。'
        elif action == 'reject':
            cert_request.status = CertificateRequest.STATUS_REJECTED
            message = '申请已在终审环节驳回。'
        else:
            raise ValueError('无效的审批动作。')
        cert_request.save()
        return message

    raise PermissionDenied('当前状态下，您不能审批该申请。')


def _build_certificate_pdf(cert_request):
    registerFont(UnicodeCIDFont('STSong-Light'))
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle(f'{cert_request.cert_type}-{_get_display_name(cert_request.applicant)}')
    pdf.setFont('STSong-Light', 20)
    pdf.drawCentredString(width / 2, height - 90, '学院电子证明')

    pdf.setFont('STSong-Light', 12)
    current_time = timezone.localtime(timezone.now())
    lines = [
        f'证明编号：CERT-{cert_request.id:05d}',
        f'证明类型：{cert_request.cert_type}',
        f'申请人：{_get_display_name(cert_request.applicant)}',
        f'学号：{cert_request.applicant.student_id or "未登记"}',
        f'专业：{cert_request.applicant.major or "未登记"}',
        f'年级：{cert_request.applicant.grade or "未登记"}',
        f'身份证号：{_mask_id_number(cert_request.applicant.id_number)}',
        f'申请用途：{cert_request.purpose}',
        '',
        '兹证明上述学生信息已由学院系统核验，电子审批流程已完成，',
        '本证明可用于校内常规事项办理与材料预审。',
        '',
        f'初审人：{_get_display_name(cert_request.first_reviewer) if cert_request.first_reviewer else "未完成"}',
        f'终审人：{_get_display_name(cert_request.final_reviewer) if cert_request.final_reviewer else "未完成"}',
        f'签发时间：{current_time.strftime("%Y-%m-%d %H:%M")}',
        '签发方式：系统自动生成 PDF',
    ]

    y = height - 140
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 24

    pdf.setFont('STSong-Light', 11)
    pdf.drawString(72, 110, '温馨提示：此页面为课程项目演示版，可作为后续接入正式模板的基础。')
    pdf.drawRightString(width - 72, 72, '学院学生综合服务与党团管理平台')
    pdf.showPage()
    pdf.save()

    filename = f'certificate_{cert_request.id}.pdf'
    cert_request.generated_pdf.save(filename, ContentFile(buffer.getvalue()), save=False)


class IndexView(TemplateView):
    """证明开具首页。"""

    template_name = 'certificate/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role_key, user = _get_demo_user(self.request)
        dashboard = _get_dashboard_context(user)

        context.update(
            {
                'cert_type_choices': CERTIFICATE_TYPE_CHOICES,
                'my_requests': dashboard['my_requests'],
                'first_review_queue': dashboard['first_review_queue'],
                'final_review_queue': dashboard['final_review_queue'],
                'current_user': user,
                'current_role_key': role_key,
                'is_student': user.role == User.ROLE_STUDENT,
                'can_first_review': user.role == User.ROLE_CADRE,
                'can_final_review': user.role in (User.ROLE_ADMIN, User.ROLE_LEADER),
            }
        )
        return context


class DemoSwitchView(View):
    """在证明模块内切换演示身份。"""

    def get(self, request, role):
        if role not in DEMO_USER_PRESETS:
            messages.error(request, '未找到对应的演示身份。')
            return redirect('certificate:index')

        request.session['certificate_demo_role'] = role
        _, user = _get_demo_user(request)
        messages.success(request, f'当前演示身份已切换为{_get_display_name(user)}。')
        return redirect('certificate:index')


class ApplyView(View):
    """学生提交证明申请。"""

    def post(self, request):
        _, current_user = _get_demo_user(request)
        cert_type = request.POST.get('cert_type', '').strip()
        purpose = request.POST.get('purpose', '').strip()
        try:
            _create_certificate_request(current_user, cert_type, purpose)
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
            return redirect('certificate:index')
        messages.success(request, '证明申请已提交，等待老师审批。')
        return redirect('certificate:index')


class ReviewView(View):
    """老师在线审批。"""

    def post(self, request, pk):
        _, current_user = _get_demo_user(request)
        cert_request = get_object_or_404(
            CertificateRequest.objects.select_related('applicant', 'first_reviewer', 'final_reviewer'),
            pk=pk,
        )
        action = request.POST.get('action')
        try:
            message = _review_certificate_request(current_user, cert_request, action)
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
            return redirect('certificate:index')
        messages.success(request, message)
        return redirect('certificate:index')


class DownloadView(View):
    """下载已生成的 PDF 证明。"""

    def get(self, request, pk):
        _, current_user = _get_demo_user(request)
        cert_request = get_object_or_404(CertificateRequest.objects.select_related('applicant'), pk=pk)
        if cert_request.status != CertificateRequest.STATUS_APPROVED or not cert_request.generated_pdf:
            raise PermissionDenied('该证明尚未生成。')
        if current_user != cert_request.applicant and current_user.role not in (User.ROLE_ADMIN, User.ROLE_LEADER):
            raise PermissionDenied('您无权下载该证明。')

        return FileResponse(
            cert_request.generated_pdf.open('rb'),
            as_attachment=True,
            filename=os.path.basename(cert_request.generated_pdf.name),
        )


@router.get('/overview')
def api_overview(request):
    role_key, user = _get_demo_user(request)
    dashboard = _get_dashboard_context(user)
    return success(
        data={
            'current_role_key': role_key,
            'current_user': _serialize_user(user),
            'cert_type_choices': CERTIFICATE_TYPE_CHOICES,
            'my_requests': [_serialize_request(item) for item in dashboard['my_requests']],
            'first_review_queue': [_serialize_request(item) for item in dashboard['first_review_queue']],
            'final_review_queue': [_serialize_request(item) for item in dashboard['final_review_queue']],
        }
    )


@router.post('/demo/{role}')
def api_switch_demo_role(request, role: str):
    if role not in DEMO_USER_PRESETS:
        return error(msg='未找到对应的演示身份。', code=404)
    request.session['certificate_demo_role'] = role
    _, user = _get_demo_user(request)
    return success(
        data={
            'current_role_key': role,
            'current_user': _serialize_user(user),
        },
        msg=f'当前演示身份已切换为{_get_display_name(user)}。',
    )


@router.post('/apply')
def api_apply(request, payload: CertificateApplyIn):
    _, current_user = _get_demo_user(request)
    try:
        cert_request = _create_certificate_request(
            current_user,
            payload.cert_type.strip(),
            payload.purpose.strip(),
        )
    except PermissionDenied as exc:
        return error(msg=str(exc), code=403)
    except ValueError as exc:
        return error(msg=str(exc), code=400)
    return success(data=_serialize_request(cert_request), msg='证明申请已提交，等待老师审批。')


@router.post('/{pk}/review')
def api_review(request, pk: int, payload: CertificateReviewIn):
    _, current_user = _get_demo_user(request)
    cert_request = get_object_or_404(
        CertificateRequest.objects.select_related('applicant', 'first_reviewer', 'final_reviewer'),
        pk=pk,
    )
    try:
        message = _review_certificate_request(current_user, cert_request, payload.action.strip())
    except PermissionDenied as exc:
        return error(msg=str(exc), code=403)
    except ValueError as exc:
        return error(msg=str(exc), code=400)
    cert_request.refresh_from_db()
    return success(data=_serialize_request(cert_request), msg=message)


@router.get('/{pk}')
def api_detail(request, pk: int):
    _get_demo_user(request)
    cert_request = get_object_or_404(
        CertificateRequest.objects.select_related('applicant', 'first_reviewer', 'final_reviewer'),
        pk=pk,
    )
    return success(data=_serialize_request(cert_request))
