import django.contrib.auth.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_user_employee_id"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="user",
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
    ]
