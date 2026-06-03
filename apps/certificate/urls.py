from django.urls import path

from . import views

app_name = "certificate"

urlpatterns = [
    path("", views.ListView.as_view(), name="index"),
    path("new/", views.CreateView.as_view(), name="create"),
    path("preview/", views.PreviewDraftView.as_view(), name="preview_draft"),
    path("<int:pk>/", views.DetailView.as_view(), name="detail"),
    path("<int:pk>/preview/", views.PreviewView.as_view(), name="preview"),
    path("<int:pk>/resubmit/", views.ResubmitView.as_view(), name="resubmit"),
    path("<int:pk>/revoke/", views.RevokeView.as_view(), name="revoke"),
    path("<int:pk>/download/", views.DownloadView.as_view(), name="download"),
]
