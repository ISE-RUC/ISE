from django.urls import path
from . import views

app_name = 'certificate'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('demo/<str:role>/', views.DemoSwitchView.as_view(), name='demo_switch'),
    path('apply/', views.ApplyView.as_view(), name='apply'),
    path('<int:pk>/review/', views.ReviewView.as_view(), name='review'),
    path('<int:pk>/download/', views.DownloadView.as_view(), name='download'),
]
