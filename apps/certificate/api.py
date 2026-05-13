from django.utils import timezone
from ninja import Router, Schema

from utils.response import error, success

from .models import CertificateRequest
from .views import (
    CERTIFICATE_OPTIONS,
    build_request_rows,
    build_timeline,
    create_request,
    ensure_demo_user,
    get_request_or_404,
    get_student_profile,
    get_status_payload,
    option_id_from_name,
    update_request_for_resubmit,
)


router = Router(tags=["证明开具"])


class CertificateSubmitIn(Schema):
    certificate_type: str
    purpose: str
    attachment_note: str


def _detail_url(request, request_obj):
    return request.build_absolute_uri(f"/certificate/{request_obj.id}/")


def _download_url(request, request_obj):
    return request.build_absolute_uri(f"/certificate/{request_obj.id}/download/")


def _preview_url(request, request_obj):
    return request.build_absolute_uri(f"/certificate/{request_obj.id}/preview/")


def _serialize_materials(request_obj):
    return [
        {
            "id": item.id,
            "name": item.name,
            "detail": item.detail,
            "is_required": item.is_required,
            "is_valid": item.is_valid,
            "status": "校验通过" if item.is_valid else "待补充",
        }
        for item in request_obj.materials.all()
    ]


def _serialize_logs(request_obj):
    return [
        {
            "id": item.id,
            "action": item.action,
            "detail": item.detail,
            "operator": item.operator,
            "created_at": timezone.localtime(item.created_at).strftime("%Y-%m-%d %H:%M"),
        }
        for item in request_obj.logs.order_by("-created_at")
    ]


def _serialize_request_detail(request, request_obj):
    status = get_status_payload(request_obj)
    return {
        "id": request_obj.id,
        "reference": request_obj.reference_no,
        "certificate_type": option_id_from_name(request_obj.cert_type),
        "certificate_name": request_obj.cert_type,
        "purpose": request_obj.purpose,
        "attachment_note": request_obj.attachment_note,
        "rejection_reason": request_obj.rejection_reason,
        "status": status,
        "materials": _serialize_materials(request_obj),
        "timeline": build_timeline(request_obj),
        "logs": _serialize_logs(request_obj),
        "urls": {
            "detail": _detail_url(request, request_obj),
            "preview": _preview_url(request, request_obj) if status["can_preview"] else "",
            "download": _download_url(request, request_obj) if status["can_download"] else "",
        },
    }


@router.get("/types")
def list_certificate_types(request):
    data = [{"id": key, **value} for key, value in CERTIFICATE_OPTIONS.items()]
    return success(data={"types": data})


@router.get("/")
def list_certificates(request):
    student = ensure_demo_user()
    rows = []
    for row in build_request_rows(student):
        item = {**row}
        item["urls"] = {
            "detail": request.build_absolute_uri(f"/certificate/{row['id']}/"),
            "preview": request.build_absolute_uri(f"/certificate/{row['id']}/preview/")
            if row["can_preview"]
            else "",
            "download": request.build_absolute_uri(f"/certificate/{row['id']}/download/")
            if row["can_download"]
            else "",
        }
        rows.append(item)
    return success(data={"student": get_student_profile(student), "requests": rows})


@router.post("/")
def create_certificate(request, payload: CertificateSubmitIn):
    student = ensure_demo_user()
    request_obj, ok = create_request(
        student,
        payload.certificate_type,
        payload.purpose.strip(),
        payload.attachment_note.strip(),
    )
    data = {
        "id": request_obj.id,
        "detail_url": _detail_url(request, request_obj),
        "status": get_status_payload(request_obj),
        "request": _serialize_request_detail(request, request_obj),
    }
    if not ok:
        return success(data=data, msg="材料完整性校验未通过，申请已进入待补充材料状态。")
    return success(data=data, msg="申请已提交，当前等待管理员审核。")


@router.get("/{request_id}")
def get_certificate(request, request_id: int):
    student = ensure_demo_user()
    request_obj = get_request_or_404(student, request_id)
    return success(data={"request": _serialize_request_detail(request, request_obj)})


@router.post("/{request_id}/resubmit")
def resubmit_certificate(request, request_id: int, payload: CertificateSubmitIn):
    student = ensure_demo_user()
    request_obj = get_request_or_404(student, request_id)
    if request_obj.status not in {
        CertificateRequest.STATUS_MATERIAL_REJECTED,
        CertificateRequest.STATUS_REJECTED,
        CertificateRequest.STATUS_REVOKED,
    }:
        return error(msg="当前状态下不能重新提交。", code=400)

    ok = update_request_for_resubmit(
        request_obj,
        payload.certificate_type,
        payload.purpose.strip(),
        payload.attachment_note.strip(),
    )
    request_obj.refresh_from_db()
    data = {
        "id": request_obj.id,
        "detail_url": _detail_url(request, request_obj),
        "status": get_status_payload(request_obj),
        "request": _serialize_request_detail(request, request_obj),
    }
    if not ok:
        return success(data=data, msg="材料完整性校验未通过，请继续补充后再次提交。")
    return success(data=data, msg="申请已重新提交，当前等待管理员审核。")


@router.post("/{request_id}/revoke")
def revoke_certificate(request, request_id: int):
    student = ensure_demo_user()
    request_obj = get_request_or_404(student, request_id)
    if request_obj.status != CertificateRequest.STATUS_APPROVED_OBSERVING:
        return error(msg="当前状态下不能撤回。", code=400)

    request_obj.status = CertificateRequest.STATUS_REVOKED
    request_obj.revoked_at = timezone.now()
    request_obj.is_pdf_void = True
    request_obj.last_operator = "学生撤回"
    request_obj.save(update_fields=["status", "revoked_at", "is_pdf_void", "last_operator", "updated_at"])
    request_obj.logs.create(action="学生撤回", detail="学生在观察期内主动撤回申请，原文件作废。", operator="学生")
    return success(
        data={
            "id": request_obj.id,
            "detail_url": _detail_url(request, request_obj),
            "status": get_status_payload(request_obj),
            "request": _serialize_request_detail(request, request_obj),
        },
        msg="申请已撤回，原文件已作废。",
    )
