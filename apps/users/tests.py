from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.party.models import PartyMemberStatus
from apps.users.models import AuditLog, User


class UserAuthViewTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="20260001",
            student_id="20260001",
            password="party1234",
            real_name="测试学生",
            role=User.ROLE_STUDENT,
        )

    def test_home_redirects_anonymous_user_to_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/users/login/?next=/")

    def test_login_page_keeps_next_value(self):
        response = self.client.get("/users/login/?next=/party/student/timeline/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="next" value="/party/student/timeline/"')

    def test_login_supports_student_id(self):
        response = self.client.post(
            reverse("users:login"),
            {"username": "20260001", "password": "party1234", "next": "/"},
        )
        self.assertRedirects(response, "/")

    def test_register_creates_student_user_and_logs_in(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "role": User.ROLE_STUDENT,
                "real_name": "新同学",
                "student_id": "20260002",
                "employee_id": "",
                "password1": "party1234",
                "password2": "party1234",
            },
        )
        self.assertRedirects(response, "/")
        user = User.objects.get(student_id="20260002")
        self.assertEqual(user.username, "20260002")
        self.assertEqual(user.role, User.ROLE_STUDENT)
        profile = PartyMemberStatus.objects.get(user=user)
        self.assertEqual(profile.track_type, PartyMemberStatus.TrackType.PARTY)
        self.assertEqual(profile.current_stage, PartyMemberStatus.Stage.APPLICANT)

    def test_register_creates_cadre_user(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "role": User.ROLE_CADRE,
                "real_name": "骨干同学",
                "student_id": "20260012",
                "employee_id": "",
                "password1": "party1234",
                "password2": "party1234",
            },
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        user = User.objects.get(student_id="20260012")
        self.assertEqual(user.role, User.ROLE_CADRE)
        self.assertTrue(PartyMemberStatus.objects.filter(user=user).exists())

    def test_register_creates_admin_user_with_employee_id(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "role": User.ROLE_ADMIN,
                "real_name": "测试老师",
                "student_id": "",
                "employee_id": "T2026001",
                "password1": "party1234",
                "password2": "party1234",
            },
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        user = User.objects.get(employee_id="T2026001")
        self.assertEqual(user.username, "T2026001")
        self.assertEqual(user.role, User.ROLE_ADMIN)

    def test_register_creates_leader_user_with_employee_id(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "role": User.ROLE_LEADER,
                "real_name": "学院领导",
                "student_id": "",
                "employee_id": "L2026001",
                "password1": "party1234",
                "password2": "party1234",
            },
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        user = User.objects.get(employee_id="L2026001")
        self.assertEqual(user.role, User.ROLE_LEADER)

    def test_register_requires_employee_id_for_admin(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "role": User.ROLE_ADMIN,
                "real_name": "测试老师",
                "student_id": "",
                "employee_id": "",
                "password1": "party1234",
                "password2": "party1234",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "该身份必须填写教职工号")

    def test_logout_clears_session(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("users:logout"))
        self.assertRedirects(response, reverse("users:login"), fetch_redirect_response=False)

    def test_register_creates_audit_log(self):
        self.client.post(
            reverse("users:register"),
            {
                "role": User.ROLE_STUDENT,
                "real_name": "审计同学",
                "student_id": "20260003",
                "employee_id": "",
                "password1": "party1234",
                "password2": "party1234",
            },
        )
        self.assertTrue(AuditLog.objects.filter(action="POST /users/register/").exists())

    def test_api_login_and_me(self):
        response = self.client.post(
            "/api/users/login",
            data='{"username":"20260001","password":"party1234"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"default_home": "/"')

        me_response = self.client.get("/api/users/me")
        self.assertEqual(me_response.status_code, 200)
        self.assertContains(me_response, "20260001")

    def test_api_register_student(self):
        response = self.client.post(
            "/api/users/register",
            data='{"role":4,"real_name":"接口同学","student_id":"20260004","employee_id":"","password1":"party1234","password2":"party1234"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(student_id="20260004").exists())

    def test_api_register_admin(self):
        response = self.client.post(
            "/api/users/register",
            data='{"role":2,"real_name":"接口老师","student_id":"","employee_id":"T2026002","password1":"party1234","password2":"party1234"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(employee_id="T2026002")
        self.assertEqual(user.role, User.ROLE_ADMIN)

    def test_api_logout(self):
        self.client.force_login(self.student)
        response = self.client.post("/api/users/logout", content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_api_update_profile(self):
        self.client.force_login(self.student)
        response = self.client.post(
            "/api/users/me/profile",
            data='{"real_name":"更新后的学生","grade":"2026","major":"软件工程","email":"student@example.com"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.real_name, "更新后的学生")
        self.assertEqual(self.student.major, "软件工程")

    def test_api_change_password(self):
        self.client.force_login(self.student)
        response = self.client.post(
            "/api/users/me/password",
            data='{"old_password":"party1234","new_password1":"newpass123","new_password2":"newpass123"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password("newpass123"))

    def test_api_me_returns_employee_id_for_admin(self):
        admin_user = User.objects.create_user(
            username="teacher08",
            employee_id="T0008",
            password="party1234",
            real_name="管理老师",
            role=User.ROLE_ADMIN,
        )
        self.client.force_login(admin_user)
        response = self.client.get("/api/users/me")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"employee_id": "T0008"')
        self.assertContains(response, '"default_home": "/"')

    def test_user_can_view_own_detail(self):
        self.client.force_login(self.student)
        response = self.client.get(f"/api/users/{self.student.id}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"username": "20260001"')

    def test_student_cannot_view_other_user_detail(self):
        other_user = User.objects.create_user(
            username="20260009",
            student_id="20260009",
            password="party1234",
            role=User.ROLE_STUDENT,
        )
        self.client.force_login(self.student)
        response = self.client.get(f"/api/users/{other_user.id}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"code": 403')

    def test_admin_can_list_users(self):
        admin_user = User.objects.create_user(
            username="teacher04",
            employee_id="T0004",
            password="party1234",
            real_name="管理老师",
            role=User.ROLE_ADMIN,
        )
        self.client.force_login(admin_user)
        response = self.client.get("/api/users/list")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "20260001")

    def test_admin_can_create_cadre_user(self):
        admin_user = User.objects.create_user(
            username="teacher05",
            employee_id="T0005",
            password="party1234",
            real_name="管理老师",
            role=User.ROLE_ADMIN,
        )
        self.client.force_login(admin_user)
        response = self.client.post(
            "/api/users/admin/create",
            data='{"username":"cadre01","password":"party1234","real_name":"班团骨干","role":3,"student_id":"20260010","employee_id":""}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        created_user = User.objects.get(username="cadre01")
        self.assertEqual(created_user.role, User.ROLE_CADRE)
        profile = PartyMemberStatus.objects.get(user=created_user)
        self.assertEqual(profile.created_by, admin_user)

    def test_admin_cannot_create_leader_user(self):
        admin_user = User.objects.create_user(
            username="teacher06",
            employee_id="T0006",
            password="party1234",
            real_name="管理老师",
            role=User.ROLE_ADMIN,
        )
        self.client.force_login(admin_user)
        response = self.client.post(
            "/api/users/admin/create",
            data='{"username":"leader01","password":"party1234","real_name":"学院领导","role":1,"student_id":"","employee_id":"L001"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"code": 400')

    def test_leader_can_update_user_role(self):
        leader_user = User.objects.create_user(
            username="leader02",
            employee_id="L0002",
            password="party1234",
            real_name="学院领导",
            role=User.ROLE_LEADER,
        )
        cadre_user = User.objects.create_user(
            username="cadre02",
            student_id="20260022",
            password="party1234",
            real_name="骨干同学",
            role=User.ROLE_CADRE,
        )
        self.client.force_login(leader_user)
        response = self.client.post(
            f"/api/users/{cadre_user.id}/role",
            data='{"role":2}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        cadre_user.refresh_from_db()
        self.assertEqual(cadre_user.role, User.ROLE_ADMIN)

    def test_leader_promoting_student_role_creates_party_profile(self):
        leader_user = User.objects.create_user(
            username="leader03",
            employee_id="L0003",
            password="party1234",
            real_name="学院领导",
            role=User.ROLE_LEADER,
        )
        target_user = User.objects.create_user(
            username="teacher-like-user",
            employee_id="T0099",
            password="party1234",
            real_name="待转学生",
            role=User.ROLE_ADMIN,
        )
        self.client.force_login(leader_user)
        response = self.client.post(
            f"/api/users/{target_user.id}/role",
            data='{"role":4}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        target_user.refresh_from_db()
        self.assertEqual(target_user.role, User.ROLE_STUDENT)
        profile = PartyMemberStatus.objects.get(user=target_user)
        self.assertEqual(profile.created_by, leader_user)

    def test_seed_demo_users_command_creates_accounts(self):
        call_command("seed_demo_users")
        self.assertTrue(User.objects.filter(username="leader_demo", role=User.ROLE_LEADER).exists())
        self.assertTrue(User.objects.filter(username="admin_demo", role=User.ROLE_ADMIN).exists())
        self.assertTrue(User.objects.filter(username="cadre_demo", role=User.ROLE_CADRE).exists())
        self.assertTrue(User.objects.filter(username="student_demo", role=User.ROLE_STUDENT).exists())

    def test_landing_redirect_by_role(self):
        self.client.force_login(self.student)
        response = self.client.get("/users/landing/")
        self.assertRedirects(response, "/", fetch_redirect_response=False)
