from django.test import TestCase
from django.urls import reverse

from apps.users.models import User


class ProfilePageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="profile_student",
            password="pass123456",
            student_id="2026003001",
            real_name="旧姓名",
            role=User.ROLE_STUDENT,
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse("profile:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response["Location"])

    def test_profile_updates_current_user_info(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("profile:index"),
            {
                "real_name": "新姓名",
                "student_id": "2026003002",
                "grade": "2026",
                "major": "信息系统工程",
                "email": "student@example.com",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.real_name, "新姓名")
        self.assertEqual(self.user.student_id, "2026003002")
        self.assertEqual(self.user.major, "信息系统工程")
