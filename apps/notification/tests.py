from django.test import TestCase
from django.urls import reverse

from apps.notification.models import Notification
from apps.users.models import User


class NotificationPermissionTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="notice_permission_student",
            password="pass123456",
            student_id="2026004001",
            role=User.ROLE_STUDENT,
        )
        self.admin = User.objects.create_user(
            username="notice_permission_admin",
            password="pass123456",
            employee_id="T2026004001",
            role=User.ROLE_ADMIN,
        )
        self.notification = Notification.objects.create(
            title="测试通知",
            content="测试内容",
            publisher=self.admin,
        )

    def test_write_actions_require_login(self):
        for url in [
            reverse("notification:publish"),
            reverse("notification:mark_read", args=[self.notification.pk]),
            reverse("notification:mark_all_read"),
        ]:
            response = self.client.post(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/users/login/", response["Location"])

    def test_student_cannot_publish_notification(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("notification:publish"),
            {"title": "学生发布", "content": "不允许"},
        )

        self.assertEqual(response.status_code, 403)
