from django.core.management.base import BaseCommand

from apps.party.models import PartyMemberStatus
from apps.party.services import reminder


class Command(BaseCommand):
    help = "根据当前党团流程状态生成或同步提醒任务。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--member-id",
            type=int,
            help="仅为指定党团档案生成提醒。",
        )

    def handle(self, *args, **options):
        queryset = PartyMemberStatus.objects.prefetch_related("stage_instances")
        member_id = options.get("member_id")
        if member_id:
            queryset = queryset.filter(pk=member_id)

        generated_count = reminder.generate_all_member_reminders(queryset)
        self.stdout.write(self.style.SUCCESS(f"已完成提醒同步，共处理 {generated_count} 条提醒记录。"))
