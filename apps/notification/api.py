from ninja import Router, Schema
from django.db.models import Q

from apps.users.models import User
from utils.response import error, success

from .models import Notification, NotificationRead
from .views import (
    audit_notification_action,
    can_publish_notifications,
    ensure_demo_notifications,
    get_notification_user,
    notification_queryset,
    visible_notifications_for,
)


router = Router(tags=["Notification center"])


class NotificationPublishIn(Schema):
    title: str
    content: str
    target_role: int | None = None
    target_grade: str = ""
    target_major: str = ""


def _serialize_notification(item):
    return {
        "id": item.id,
        "title": item.title,
        "content": item.content,
        "publisher": item.publisher.real_name or item.publisher.username if item.publisher else "系统",
        "target_role": item.target_role,
        "target_grade": item.target_grade,
        "target_major": item.target_major,
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
        "is_read": getattr(item, "is_read", False),
    }


@router.get("/")
def list_notifications(request, status: str = "all", q: str = ""):
    ensure_demo_notifications()
    user = get_notification_user(request)
    if user is None:
        return error(msg="请先登录", code=401)
    qs = notification_queryset(user)
    if status == "unread":
        qs = qs.filter(is_read=False)
    elif status == "read":
        qs = qs.filter(is_read=True)
    elif status != "all":
        return error(msg="无效的通知状态筛选。", code=400)
    keyword = q.strip()
    if keyword:
        qs = qs.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))
    return success(
        data={
            "notifications": [_serialize_notification(item) for item in qs],
            "count": qs.count(),
            "can_publish": can_publish_notifications(user),
        }
    )


@router.get("/{notification_id}")
def get_notification(request, notification_id: int):
    ensure_demo_notifications()
    user = get_notification_user(request)
    if user is None:
        return error(msg="请先登录", code=401)
    item = notification_queryset(user).filter(id=notification_id).first()
    if item is None:
        return error(msg="通知不存在或无权查看。", code=404)
    return success(data={"notification": _serialize_notification(item)})


@router.post("/")
def publish_notification(request, payload: NotificationPublishIn):
    user = get_notification_user(request)
    if not can_publish_notifications(user):
        return error(msg="只有老师和管理员可以发布通知。", code=403)
    title = payload.title.strip()
    content = payload.content.strip()
    if not title or not content:
        return error(msg="请填写通知标题和内容。", code=400)
    if payload.target_role is not None and payload.target_role not in {
        User.ROLE_LEADER,
        User.ROLE_ADMIN,
        User.ROLE_CADRE,
        User.ROLE_STUDENT,
    }:
        return error(msg="目标角色无效。", code=400)

    item = Notification.objects.create(
        title=title,
        content=content,
        publisher=user,
        target_role=payload.target_role,
        target_grade=payload.target_grade.strip(),
        target_major=payload.target_major.strip(),
    )
    audit_notification_action(request, user, "API发布通知", item)
    item.is_read = False
    return success(data={"notification": _serialize_notification(item)}, msg="通知已发布。")


@router.post("/{notification_id}/read")
def mark_notification_read(request, notification_id: int):
    ensure_demo_notifications()
    user = get_notification_user(request)
    if user is None:
        return error(msg="请先登录", code=401)
    item = visible_notifications_for(user).filter(id=notification_id).first()
    if item is None:
        return error(msg="通知不存在或无权查看。", code=404)
    NotificationRead.objects.get_or_create(notification=item, user=user)
    return success(msg="通知已标记为已读。")


@router.post("/read-all")
def mark_all_notifications_read(request):
    ensure_demo_notifications()
    user = get_notification_user(request)
    if user is None:
        return error(msg="请先登录", code=401)
    visible = visible_notifications_for(user)
    existing_ids = set(
        NotificationRead.objects.filter(user=user, notification__in=visible).values_list(
            "notification_id", flat=True
        )
    )
    NotificationRead.objects.bulk_create(
        [
            NotificationRead(notification=item, user=user)
            for item in visible
            if item.id not in existing_ids
        ],
        ignore_conflicts=True,
    )
    return success(msg="全部可见通知已标记为已读。")
