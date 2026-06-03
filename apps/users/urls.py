from django.urls import path

from . import views

app_name = 'users'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('users/landing/', views.LandingRedirectView.as_view(), name='landing'),
    path('users/login/', views.LoginView.as_view(), name='login'),
    path('users/register/', views.RegisterView.as_view(), name='register'),
    path('users/logout/', views.LogoutView.as_view(), name='logout'),
]
