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
        response = self.client.get(reverse("profile:select"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response["Location"])

    def test_student_profile_shows_current_user(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("profile:student"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["student"], self.user)
