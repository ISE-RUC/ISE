from django.test import TestCase
from django.urls import reverse

from apps.users.models import User

from .models import CertificateRequest


class CertificatePermissionTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="20260021",
            student_id="20260021",
            password="cert1234",
            real_name="测试学生",
            role=User.ROLE_STUDENT,
        )
        self.leader = User.objects.create_user(
            username="leader21",
            employee_id="L2026021",
            password="cert1234",
            real_name="学院领导",
            role=User.ROLE_LEADER,
        )
        self.request_obj = CertificateRequest.objects.create(
            applicant=self.student,
            reference_no="CERT-20260611-0001",
            cert_type="在读证明",
            purpose="测试用途",
            attachment_note="测试附件",
            status=CertificateRequest.STATUS_REJECTED,
            rejection_reason="请补充说明",
            last_operator="管理老师",
        )

    def test_leader_viewing_other_student_request_should_not_see_resubmit_button(self):
        self.client.force_login(self.leader)

        response = self.client.get(reverse("certificate:detail", args=[self.request_obj.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "重新提交申请")

    def test_leader_cannot_resubmit_other_student_request(self):
        self.client.force_login(self.leader)

        response = self.client.post(
            reverse("certificate:resubmit", args=[self.request_obj.id]),
            {
                "certificate_type": "study-status",
                "purpose": "领导代提",
                "attachment_note": "领导代提",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "仅申请提交人可重新提交该申请。")
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, CertificateRequest.STATUS_REJECTED)
