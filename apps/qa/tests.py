from django.test import TestCase
from django.urls import reverse

from apps.qa.models import FAQEntry
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

    def test_qa_search_returns_faq_results(self):
        FAQEntry.objects.create(question="国奖申请条件是什么", answer="请以学院通知为准。")
        self.client.force_login(self.user)

        response = self.client.get(reverse("qa:index"), {"q": "国奖"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "国奖申请条件是什么")
