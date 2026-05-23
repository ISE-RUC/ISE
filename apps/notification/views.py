from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.users.models import User
from apps.users.models import AuditLog

from .models import Notification, NotificationRead


DEMO_NOTIFICATIONS = [
    {
        "title": "2026届互联网企业春招信息汇总已发布",
        "content": "就业服务办公室更新了近期互联网企业招聘日程、投递入口和宣讲会安排，请毕业年级同学及时查看。",
        "target_grade": "2026",
        "target_major": "",
        "target_role": User.ROLE_STUDENT,
    },
    {
        "title": "积极分子思想汇报提交截止提醒",
        "content": "党团事务模块已同步本月思想汇报提交要求，请相关同学在截止日前完成材料上传。",
        "target_grade": "",
        "target_major": "",
        "target_role": User.ROLE_STUDENT,
    },
    {
        "title": "学生证明模板已更新",
        "content": "证明申请模块已启用新版电子证明模板，后续办理请以系统生成文件为准。",
        "target_grade": "",
        "target_major": "",
        "target_role": None,
    },
    {
        "title": "学院综合服务平台维护通知",
        "content": "本周五晚间将进行短时维护，维护期间部分查询和下载功能可能出现短暂不可用。",
        "target_grade": "",
        "target_major": "",
        "target_role": None,
    },
]


def ensure_demo_user():
    user, created = User.objects.get_or_create(
        username="notification_demo_student",
        defaults={
            "real_name": "演示学生",
            "student_id": "2026001001",
            "grade": "2026",
            "major": "信息系统工程",
            "email": "notification-demo@example.com",
            "role": User.ROLE_STUDENT,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def get_notification_user(request):
    if request.user.is_authenticated:
        return request.user
    return None


def can_publish_notifications(user):
    return bool(user and user.is_authenticated and user.can_publish_notice())


def ensure_demo_notifications():
    publisher = User.objects.filter(role__lte=User.ROLE_ADMIN).order_by("id").first()
    if publisher is None:
        publisher = ensure_demo_user()
    for item in DEMO_NOTIFICATIONS:
        Notification.objects.get_or_create(
            title=item["title"],
            defaults={
                "content": item["content"],
                "publisher": publisher,
                "target_grade": item["target_grade"],
                "target_major": item["target_major"],
                "target_role": item["target_role"],
            },
        )


def visible_notifications_for(user):
    role_filter = Q(target_role__isnull=True) | Q(target_role=user.role)
    grade_filter = Q(target_grade="") | Q(target_grade=user.grade)
    major_filter = Q(target_major="") | Q(target_major=user.major)
    return Notification.objects.filter(role_filter, grade_filter, major_filter)


def notification_queryset(user):
    read_state = NotificationRead.objects.filter(notification=OuterRef("pk"), user=user)
    return visible_notifications_for(user).annotate(is_read=Exists(read_state)).select_related("publisher")


def audit_notification_action(request, user, action, notification):
    if not user.is_authenticated:
        return
    AuditLog.objects.create(
        user=user,
        action=action,
        target_model="Notification",
        target_id=str(notification.id),
        detail=f"{notification.title}",
        ip_address=get_client_ip(request),
    )


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def get_home_notification_summary(request=None, limit=3):
    ensure_demo_notifications()
    user = get_notification_user(request) if request is not None else None
    if user is None:
        return {
            "notification_user": None,
            "home_notifications": [],
            "home_unread_count": 0,
            "can_publish_notifications": False,
        }
    qs = notification_queryset(user)
    unread = qs.filter(is_read=False)
    return {
        "notification_user": user,
        "home_notifications": list(unread[:limit]),
        "home_unread_count": unread.count(),
        "can_publish_notifications": can_publish_notifications(user),
    }


class IndexView(LoginRequiredMixin, TemplateView):
    """通知公告首页。"""

    template_name = "notification/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ensure_demo_notifications()
        user = self.request.user
        qs = notification_queryset(user)

        status = self.request.GET.get("status", "all")
        keyword = self.request.GET.get("q", "").strip()
        if status == "unread":
            qs = qs.filter(is_read=False)
        elif status == "read":
            qs = qs.filter(is_read=True)
        if keyword:
            qs = qs.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))

        all_notifications = notification_queryset(user)
        context.update(
            {
                "current_user": user,
                "notifications": qs,
                "status_filter": status,
                "keyword": keyword,
                "total_count": all_notifications.count(),
                "unread_count": all_notifications.filter(is_read=False).count(),
                "read_count": all_notifications.filter(is_read=True).count(),
                "can_publish": can_publish_notifications(user),
                "now": timezone.now(),
            }
        )
        return context


class PublishView(View):
    def post(self, request):
        user = get_notification_user(request)
        if not can_publish_notifications(user):
            raise PermissionDenied("只有老师和管理员可以发布通知。")

        title = request.POST.get("title", "").strip()
        content = request.POST.get("content", "").strip()
        target_grade = request.POST.get("target_grade", "").strip()
        target_major = request.POST.get("target_major", "").strip()
        target_role_raw = request.POST.get("target_role", "").strip()

        if not title or not content:
            messages.error(request, "请填写通知标题和内容。")
            return redirect("notification:index")

        try:
            target_role = int(target_role_raw) if target_role_raw else None
        except ValueError:
            messages.error(request, "目标角色无效。")
            return redirect("notification:index")
        if target_role is not None and target_role not in {
            User.ROLE_LEADER,
            User.ROLE_ADMIN,
            User.ROLE_CADRE,
            User.ROLE_STUDENT,
        }:
            messages.error(request, "目标角色无效。")
            return redirect("notification:index")

        notification = Notification.objects.create(
            title=title,
            content=content,
            publisher=user,
            target_grade=target_grade,
            target_major=target_major,
            target_role=target_role,
        )
        audit_notification_action(request, user, "发布通知", notification)
        messages.success(request, "通知已发布。")
        return redirect("notification:index")


class MarkReadView(View):
    def post(self, request, pk):
        ensure_demo_notifications()
        user = get_notification_user(request)
        if user is None:
            raise PermissionDenied("请先登录。")
        notification = visible_notifications_for(user).filter(pk=pk).first()
        if notification:
            NotificationRead.objects.get_or_create(notification=notification, user=user)
            messages.success(request, "通知已标记为已读。")
        return redirect("notification:index")


class MarkAllReadView(View):
    def post(self, request):
        ensure_demo_notifications()
        user = get_notification_user(request)
        if user is None:
            raise PermissionDenied("请先登录。")
        visible = visible_notifications_for(user)
        existing_ids = set(
            NotificationRead.objects.filter(user=user, notification__in=visible).values_list(
                "notification_id", flat=True
            )
        )
        NotificationRead.objects.bulk_create(
            [
                NotificationRead(notification=notification, user=user)
                for notification in visible
                if notification.id not in existing_ids
            ],
            ignore_conflicts=True,
        )
        messages.success(request, "全部可见通知已标记为已读。")
        return redirect("notification:index")
