from django.urls import path
from . import views

app_name = 'notification'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('publish/', views.PublishView.as_view(), name='publish'),
    path('<int:pk>/read/', views.MarkReadView.as_view(), name='mark_read'),
    path('read-all/', views.MarkAllReadView.as_view(), name='mark_all_read'),
]
