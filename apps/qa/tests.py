from django.test import TestCase
from django.urls import reverse

from apps.users.models import User


class QAPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="qa_student",
            password="pass123456",
            student_id="2026002001",
            role=User.ROLE_STUDENT,
        )

    def test_qa_requires_login(self):
        response = self.client.get(reverse("qa:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response["Location"])

    def test_qa_page_creates_active_conversation(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("qa:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["active_conversation_id"])
        self.assertGreaterEqual(len(response.context["chat_messages"]), 1)
