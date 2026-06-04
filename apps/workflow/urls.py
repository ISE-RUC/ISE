from django.urls import path
from . import views

app_name = 'workflow'

urlpatterns = [
    path('', views.SelectView.as_view(), name='select'),
    path('student/', views.StudentView.as_view(), name='student'),
    path('student/<int:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('admin/', views.AdminView.as_view(), name='admin'),
    path('admin/<int:pk>/', views.AdminDetailView.as_view(), name='admin_detail'),
    path('admin/template/create/', views.CreateTemplateView.as_view(), name='create_template'),
    path('admin/template/<int:pk>/delete/', views.DeleteTemplateView.as_view(), name='delete_template'),
    path('student/instance/create/', views.CreateInstanceView.as_view(), name='create_instance'),
    path('admin/<int:pk>/review/', views.ReviewStepView.as_view(), name='review_step'),
    path('admin/<int:pk>/delete/', views.DeleteInstanceView.as_view(), name='delete_instance'),
]
