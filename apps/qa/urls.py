from django.urls import path
from . import views

app_name = 'qa'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('chat/', views.ChatMessageView.as_view(), name='chat'),
    path('new/', views.NewConversationView.as_view(), name='new'),
    path('switch/', views.SwitchConversationView.as_view(), name='switch'),
    path('reset/', views.ResetConversationView.as_view(), name='reset'),
]
