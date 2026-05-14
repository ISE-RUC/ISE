from django.urls import include, path

from . import views

app_name = "party"

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("student/", include("apps.party.urls_student")),
    path("admin/", include("apps.party.urls_admin")),
]
