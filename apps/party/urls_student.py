from django.urls import path

from . import views

app_name = "party_student"

urlpatterns = [
    path("", views.StudentDashboardView.as_view(), name="dashboard"),
    path("timeline/", views.StudentTimelineView.as_view(), name="timeline"),
    path("materials/", views.StudentMaterialsView.as_view(), name="materials"),
    path("reminders/", views.StudentReminderListView.as_view(), name="reminders"),
    path("history/", views.StudentHistoryView.as_view(), name="history"),
]
