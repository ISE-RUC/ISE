from django.urls import path

from . import views

app_name = "party_admin"

urlpatterns = [
    path("", views.AdminDashboardView.as_view(), name="dashboard"),
    path("members/", views.AdminMemberListView.as_view(), name="members"),
    path("members/<int:member_id>/", views.AdminMemberDetailView.as_view(), name="member_detail"),
    path("approvals/", views.AdminApprovalListView.as_view(), name="approvals"),
    path("reminders/", views.AdminReminderOverviewView.as_view(), name="reminders"),
    path("rules/", views.AdminRuleListView.as_view(), name="rules"),
    path("import/", views.AdminImportExportView.as_view(), name="import_export"),
]
