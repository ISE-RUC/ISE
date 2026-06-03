from django.core.management.base import BaseCommand

from apps.party.services import reminder


class Command(BaseCommand):
    help = "发送到期的党团站内提醒（当前实现为标记为已发送）。"

    def handle(self, *args, **options):
        sent_count = reminder.mark_due_reminders_as_sent()
        self.stdout.write(self.style.SUCCESS(f"已发送 {sent_count} 条到期提醒。"))
