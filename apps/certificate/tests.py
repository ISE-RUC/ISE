import json

from django.test import TestCase
from django.urls import reverse

from apps.certificate.models import CertificateRequest
from apps.users.models import User


class CertificateCurrentUserTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="user_a",
            password="pass123456",
            student_id="2147483648",
            real_name="用户甲",
            major="软件工程",
            role=User.ROLE_STUDENT,
        )
        self.demo_user = User.objects.create_user(
            username="demo_student",
            password="demo123456",
            student_id="2023123456",
            real_name="张晓晴",
            major="软件工程",
            role=User.ROLE_STUDENT,
        )

    def test_certificate_create_page_uses_logged_in_user_and_topbar_state(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("certificate:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "用户甲")
        self.assertContains(response, "2147483648")
        self.assertNotContains(response, "张晓晴")
        self.assertNotContains(response, 'href="/users/login/"')
        self.assertNotContains(response, 'href="/users/register/"')

    def test_certificate_post_creates_request_for_logged_in_user(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("certificate:create"),
            data={
                "certificate_type": "study-status",
                "purpose": "竞赛报名",
                "attachment_note": "报名通知截图已上传线下材料。",
            },
        )

        self.assertEqual(response.status_code, 302)
        request_obj = CertificateRequest.objects.latest("id")
        self.assertEqual(request_obj.applicant, self.student)
        self.assertNotEqual(request_obj.applicant, self.demo_user)