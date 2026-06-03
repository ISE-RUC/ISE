import json

from django.test import TestCase
from django.urls import reverse

from apps.certificate.models import CertificateRequest
from apps.certificate.views import get_certificate_student_record
from apps.users.models import User


class CertificateCurrentUserTests(TestCase):
    def setUp(self):
        self.student_a = User.objects.create_user(
            username="student_a",
            password="pass123456",
            student_id="2026001001",
            real_name="李明",
            major="软件工程",
            role=User.ROLE_STUDENT,
        )
        self.student_b = User.objects.create_user(
            username="student_b",
            password="pass123456",
            student_id="2026001002",
            real_name="王芳",
            major="人工智能",
            role=User.ROLE_STUDENT,
        )

    def test_certificate_page_uses_logged_in_user_profile(self):
        self.client.force_login(self.student_a)

        response = self.client.get(reverse("certificate:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "李明")
        self.assertContains(response, "2026001001")
        self.assertContains(response, '<a class="btn" href="/">李明</a>', html=True)
        self.assertNotContains(response, 'href="/users/login/"')
        self.assertNotContains(response, 'href="/users/register/"')
        self.assertNotContains(response, "张晓晴")

    def test_certificate_student_record_uses_authenticated_user_object(self):
        xiaoqing = User.objects.create_user(
            username="zhangxiaoqing",
            password="pass123456",
            student_id="2147483648",
            real_name="张晓晴",
            major="计算机科学",
            role=User.ROLE_STUDENT,
        )
        self.student_a.student_id = xiaoqing.student_id
        self.student_a.real_name = "用户甲"
        resolved_student = get_certificate_student_record(self.student_a)

        self.assertIs(resolved_student, self.student_a)
        self.assertNotEqual(resolved_student, xiaoqing)

    def test_certificate_api_creates_request_for_logged_in_user(self):
        self.client.force_login(self.student_b)

        response = self.client.post(
            "/api/certificates/",
            data=json.dumps(
                {
                    "certificate_type": "study-status",
                    "purpose": "竞赛报名",
                    "attachment_note": "报名通知截图已上传线下材料。",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        request_obj = CertificateRequest.objects.get(id=payload["data"]["id"])
        self.assertEqual(request_obj.applicant, self.student_b)

    def test_user_cannot_view_another_users_certificate_request(self):
        request_obj = CertificateRequest.objects.create(
            applicant=self.student_a,
            reference_no="CERT-TEST-OTHER-0001",
            cert_type="在读证明",
            purpose="测试",
        )
        self.client.force_login(self.student_b)

        response = self.client.get(reverse("certificate:detail", args=[request_obj.id]))

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_preview_another_users_certificate_request(self):
        request_obj = CertificateRequest.objects.create(
            applicant=self.student_a,
            reference_no="CERT-TEST-OTHER-0002",
            cert_type="在读证明",
            purpose="测试",
            status=CertificateRequest.STATUS_PENDING_REVIEW,
        )
        self.client.force_login(self.student_b)

        response = self.client.get(reverse("certificate:preview", args=[request_obj.id]))

        self.assertEqual(response.status_code, 404)

    def test_pending_request_can_generate_pdf_preview(self):
        request_obj = CertificateRequest.objects.create(
            applicant=self.student_a,
            reference_no="CERT-TEST-PREVIEW-0001",
            cert_type="在读证明",
            purpose="竞赛报名",
            status=CertificateRequest.STATUS_PENDING_REVIEW,
        )
        self.client.force_login(self.student_a)

        response = self.client.get(reverse("certificate:preview", args=[request_obj.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_missing_name_can_still_create_certificate_with_student_id(self):
        incomplete = User.objects.create_user(
            username="2026001999",
            password="pass123456",
            student_id="2026001999",
            role=User.ROLE_STUDENT,
        )
        self.client.force_login(incomplete)

        page_response = self.client.get(reverse("certificate:create"))
        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, "2026001999")
        self.assertNotContains(page_response, "学生基础信息不完整")

        api_response = self.client.post(
            "/api/certificates/",
            data=json.dumps(
                {
                    "certificate_type": "study-status",
                    "purpose": "竞赛报名",
                    "attachment_note": "报名通知截图已上传线下材料。",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(api_response.status_code, 200)
        payload = api_response.json()
        self.assertEqual(payload["code"], 0)
        request_obj = CertificateRequest.objects.get(id=payload["data"]["id"])
        self.assertEqual(request_obj.applicant, incomplete)
