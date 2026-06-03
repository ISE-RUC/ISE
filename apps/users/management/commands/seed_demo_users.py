from django.core.management.base import BaseCommand

from apps.users.models import User


DEMO_USERS = [
    {
        "username": "leader_demo",
        "password": "password123",
        "real_name": "学院领导",
        "role": User.ROLE_LEADER,
        "employee_id": "T0001",
    },
    {
        "username": "admin_demo",
        "password": "password123",
        "real_name": "管理老师",
        "role": User.ROLE_ADMIN,
        "employee_id": "T0002",
    },
    {
        "username": "cadre_demo",
        "password": "password123",
        "real_name": "班团骨干",
        "role": User.ROLE_CADRE,
        "student_id": "2026002001",
        "grade": "2026",
        "major": "信息系统工程",
    },
    {
        "username": "student_demo",
        "password": "password123",
        "real_name": "普通学生",
        "role": User.ROLE_STUDENT,
        "student_id": "2026001001",
        "grade": "2026",
        "major": "信息系统工程",
    },
]


class Command(BaseCommand):
    help = "Create demo users for login and notification permission testing."

    def handle(self, *args, **options):
        for item in DEMO_USERS:
            password = item.pop("password")
            user, created = User.objects.update_or_create(
                username=item["username"],
                defaults={**item, "email": f"{item['username']}@example.com"},
            )
            user.set_password(password)
            user.save(update_fields=["password"])
            label = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"{label}: {user.username} / {password}"))
