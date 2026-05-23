from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from config.api import api

urlpatterns = [
    path('admin/', admin.site.urls),
    # API 路由 (自动生成文档在 /api/docs/)
    path('api/', api.urls),
    # 应用路由
    path('', include('apps.users.urls', namespace='users')),
    path('qa/', include('apps.qa.urls', namespace='qa')),
    path('party/', include('apps.party.urls', namespace='party')),
    path('certificate/', include('apps.certificate.urls', namespace='certificate')),
    path('notification/', include('apps.notification.urls', namespace='notification')),
    path('profile/', include('apps.profile.urls', namespace='profile')),
    path('workflow/', include('apps.workflow.urls', namespace='workflow')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
