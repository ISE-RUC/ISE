from django.urls import path
from . import views

app_name = 'profile'

urlpatterns = [
    path('', views.SelectView.as_view(), name='select'),
    path('set-student/', views.SetStudentView.as_view(), name='set_student'),
    path('student/', views.StudentView.as_view(), name='student'),
    path('admin/', views.AdminView.as_view(), name='admin'),
    path('admin/add/', views.AddHonorView.as_view(), name='add'),
    path('admin/<int:pk>/delete/', views.DeleteHonorView.as_view(), name='delete'),
]
