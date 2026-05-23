from django.core.management.base import BaseCommand
from django.db import transaction

from apps.users.models import User


DEMO_USER_SEEDS = [
    {
        "username": "leader_demo",
        "real_name": "学院领导演示账号",
        "role": User.ROLE_LEADER,
        "student_id": "",
        "employee_id": "leader_demo",
        "grade": "",
        "major": "信息学院",
        "email": "leader_demo@example.com",
    },
    {
        "username": "admin_demo",
        "real_name": "管理老师演示账号",
        "role": User.ROLE_ADMIN,
        "student_id": "",
        "employee_id": "admin_demo",
        "grade": "",
        "major": "信息学院",
        "email": "admin_demo@example.com",
    },
    {
        "username": "cadre_demo",
        "real_name": "班团骨干演示账号",
        "role": User.ROLE_CADRE,
        "student_id": "20260010",
        "employee_id": "",
        "grade": "2026",
        "major": "信息管理",
        "email": "cadre_demo@example.com",
    },
    {
        "username": "student_demo",
        "real_name": "普通学生演示账号",
        "role": User.ROLE_STUDENT,
        "student_id": "20260011",
        "employee_id": "",
        "grade": "2026",
        "major": "信息管理",
        "email": "student_demo@example.com",
    },
]


class Command(BaseCommand):
    help = "创建或更新四类演示账号，默认密码为 party1234"

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for seed in DEMO_USER_SEEDS:
            username = seed["username"]
            defaults = {
                "real_name": seed["real_name"],
                "role": seed["role"],
                "grade": seed["grade"],
                "major": seed["major"],
                "email": seed["email"],
                "student_id": seed["student_id"] or None,
                "employee_id": seed["employee_id"] or None,
            }
            user, created = User.objects.get_or_create(username=username, defaults=defaults)

            changed_fields = []
            if created:
                created_count += 1
            else:
                for field, value in defaults.items():
                    if getattr(user, field) != value:
                        setattr(user, field, value)
                        changed_fields.append(field)
                if changed_fields:
                    user.save(update_fields=changed_fields)
                    updated_count += 1

            user.set_password("party1234")
            user.save(update_fields=["password"])

            self.stdout.write(
                self.style.SUCCESS(
                    f"{'Created' if created else 'Updated'} demo user: {username} / {user.get_role_display()}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created_count}, updated={updated_count}, password=party1234"
            )
        )
