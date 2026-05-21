from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db import transaction

from apps.party.models import (
    PartyMaterialType,
    PartyMemberStatus,
    PartyStageDefinition,
    PartyStageMaterialRequirement,
)
from apps.party.services.workflow import initialize_member_workflow
from apps.users.models import User


PARTY_STAGE_SEEDS = [
    {
        "code": "party_applicant",
        "name": "入党申请人",
        "stage": PartyMemberStatus.Stage.APPLICANT,
        "order": 1,
        "min_duration_days": 0,
        "materials": ["application_letter"],
    },
    {
        "code": "party_activist",
        "name": "积极分子",
        "stage": PartyMemberStatus.Stage.ACTIVIST,
        "order": 2,
        "min_duration_days": 90,
        "materials": ["thought_report"],
    },
    {
        "code": "party_candidate",
        "name": "发展对象",
        "stage": PartyMemberStatus.Stage.CANDIDATE,
        "order": 3,
        "min_duration_days": 365,
        "materials": ["training_certificate"],
    },
    {
        "code": "party_probationary",
        "name": "预备党员",
        "stage": PartyMemberStatus.Stage.PROBATIONARY,
        "order": 4,
        "min_duration_days": 365,
        "materials": ["personal_summary"],
    },
    {
        "code": "party_full",
        "name": "正式党员",
        "stage": PartyMemberStatus.Stage.FULL,
        "order": 5,
        "min_duration_days": 0,
        "materials": ["branch_opinion"],
    },
]

LEAGUE_STAGE_SEEDS = [
    {
        "code": "league_applicant",
        "name": "入团申请人",
        "stage": PartyMemberStatus.Stage.APPLICANT,
        "order": 1,
        "min_duration_days": 0,
        "materials": ["league_application"],
    },
    {
        "code": "league_activist",
        "name": "入团积极分子",
        "stage": PartyMemberStatus.Stage.ACTIVIST,
        "order": 2,
        "min_duration_days": 30,
        "materials": ["league_thought_report"],
    },
    {
        "code": "league_candidate",
        "name": "入团发展对象",
        "stage": PartyMemberStatus.Stage.CANDIDATE,
        "order": 3,
        "min_duration_days": 60,
        "materials": ["league_training_certificate"],
    },
    {
        "code": "league_probationary",
        "name": "团员发展公示",
        "stage": PartyMemberStatus.Stage.PROBATIONARY,
        "order": 4,
        "min_duration_days": 30,
        "materials": ["league_public_notice"],
    },
    {
        "code": "league_full",
        "name": "正式团员",
        "stage": PartyMemberStatus.Stage.FULL,
        "order": 5,
        "min_duration_days": 0,
        "materials": ["league_branch_record"],
    },
]

MATERIAL_TYPE_SEEDS = [
    {
        "code": "application_letter",
        "name": "入党申请书",
        "description": "首次申请阶段提交的基础材料。",
        "allowed_extensions": "pdf,doc,docx",
    },
    {
        "code": "thought_report",
        "name": "思想汇报",
        "description": "积极分子阶段提交的思想汇报材料。",
        "allowed_extensions": "pdf,doc,docx",
    },
    {
        "code": "training_certificate",
        "name": "培训证明",
        "description": "发展对象阶段提交的培训合格证明。",
        "allowed_extensions": "pdf,jpg,jpeg,png",
    },
    {
        "code": "personal_summary",
        "name": "个人总结",
        "description": "预备党员阶段提交的个人总结。",
        "allowed_extensions": "pdf,doc,docx",
    },
    {
        "code": "branch_opinion",
        "name": "支部意见",
        "description": "正式党员阶段留档材料。",
        "allowed_extensions": "pdf,doc,docx",
    },
    {
        "code": "league_application",
        "name": "入团申请书",
        "description": "入团申请阶段提交的基础材料。",
        "allowed_extensions": "pdf,doc,docx",
    },
    {
        "code": "league_thought_report",
        "name": "团课心得",
        "description": "入团积极分子阶段提交的团课心得或思想汇报。",
        "allowed_extensions": "pdf,doc,docx",
    },
    {
        "code": "league_training_certificate",
        "name": "团校培训证明",
        "description": "入团发展对象阶段提交的培训合格证明。",
        "allowed_extensions": "pdf,jpg,jpeg,png",
    },
    {
        "code": "league_public_notice",
        "name": "发展公示材料",
        "description": "团员发展公示阶段留档材料。",
        "allowed_extensions": "pdf,doc,docx",
    },
    {
        "code": "league_branch_record",
        "name": "支部大会记录",
        "description": "正式团员阶段留档材料。",
        "allowed_extensions": "pdf,doc,docx",
    },
]


TRACK_STAGE_SEEDS = {
    PartyMemberStatus.TrackType.PARTY: PARTY_STAGE_SEEDS,
    PartyMemberStatus.TrackType.LEAGUE: LEAGUE_STAGE_SEEDS,
}


class Command(BaseCommand):
    help = "初始化 party 模块最小闭环所需的流程节点、材料类型与可选演示账号。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-demo-users",
            action="store_true",
            help="同时创建演示学生与管理老师，并为学生初始化首个流程节点。",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        material_type_map = {}
        for item in MATERIAL_TYPE_SEEDS:
            material_type, _ = PartyMaterialType.objects.update_or_create(
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "description": item["description"],
                    "allowed_extensions": item["allowed_extensions"],
                    "max_size_mb": 30,
                    "is_active": True,
                },
            )
            material_type_map[item["code"]] = material_type

        for track_type, stage_seeds in TRACK_STAGE_SEEDS.items():
            for item in stage_seeds:
                stage_definition, _ = PartyStageDefinition.objects.update_or_create(
                    track_type=track_type,
                    code=item["code"],
                    defaults={
                        "name": item["name"],
                        "stage": item["stage"],
                        "order": item["order"],
                        "min_duration_days": item["min_duration_days"],
                        "requires_training": item["code"] in {
                            "party_candidate",
                            "league_candidate",
                        },
                        "target_role_for_approval": User.ROLE_ADMIN,
                        "is_active": True,
                        "description": f"{item['name']} 阶段默认节点定义",
                    },
                )

                expected_material_codes = set(item["materials"])
                PartyStageMaterialRequirement.objects.filter(
                    stage_definition=stage_definition
                ).exclude(material_type__code__in=expected_material_codes).delete()

                for order, material_code in enumerate(item["materials"], start=1):
                    PartyStageMaterialRequirement.objects.update_or_create(
                        stage_definition=stage_definition,
                        material_type=material_type_map[material_code],
                        defaults={
                            "is_required": True,
                            "note": "最小闭环默认必需材料",
                            "order": order,
                        },
                    )

        self.stdout.write(self.style.SUCCESS("党团流程定义和材料类型已初始化。"))

        if options["with_demo_users"]:
            existing_tables = set(connection.introspection.table_names())
            if "users_user" not in existing_tables:
                raise CommandError(
                    "当前数据库缺少 users_user 表。请先应用 users 迁移，或使用 --settings=config.settings_testdb 在新库中初始化演示数据。"
                )
            teacher, _ = User.objects.get_or_create(
                username="party_admin",
                defaults={
                    "role": User.ROLE_ADMIN,
                    "real_name": "党团管理员",
                    "email": "party_admin@example.com",
                },
            )
            teacher.set_password("party1234")
            teacher.save(update_fields=["password"])

            student, _ = User.objects.get_or_create(
                username="party_student",
                defaults={
                    "role": User.ROLE_STUDENT,
                    "real_name": "示例学生",
                    "student_id": "20260001",
                    "major": "信息管理",
                    "grade": "2026",
                    "email": "party_student@example.com",
                },
            )
            student.set_password("party1234")
            student.save(update_fields=["password"])

            league_student, _ = User.objects.get_or_create(
                username="league_student",
                defaults={
                    "role": User.ROLE_STUDENT,
                    "real_name": "入团示例学生",
                    "student_id": "20260002",
                    "major": "信息安全",
                    "grade": "2026",
                    "email": "league_student@example.com",
                },
            )
            league_student.set_password("party1234")
            league_student.save(update_fields=["password"])

            member, _ = PartyMemberStatus.objects.get_or_create(
                user=student,
                defaults={
                    "track_type": PartyMemberStatus.TrackType.PARTY,
                    "current_stage": PartyMemberStatus.Stage.APPLICANT,
                    "created_by": teacher,
                },
            )
            initialize_member_workflow(member, operator=teacher)

            league_member, _ = PartyMemberStatus.objects.get_or_create(
                user=league_student,
                defaults={
                    "track_type": PartyMemberStatus.TrackType.LEAGUE,
                    "current_stage": PartyMemberStatus.Stage.APPLICANT,
                    "created_by": teacher,
                },
            )
            initialize_member_workflow(league_member, operator=teacher)
            self.stdout.write(
                self.style.SUCCESS(
                    "演示账号已创建：party_admin / party1234, party_student / party1234, league_student / party1234"
                )
            )
