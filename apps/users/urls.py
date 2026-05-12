from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('users/login/', views.UserLoginView.as_view(), name='login'),
    path('users/logout/', views.UserLogoutView.as_view(), name='logout'),
]
