from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.users.urls', namespace='users')),
    path('qa/', include('apps.qa.urls', namespace='qa')),
    path('party/', include('apps.party.urls', namespace='party')),
    path('certificate/', include('apps.certificate.urls', namespace='certificate')),
    path('notification/', include('apps.notification.urls', namespace='notification')),
    path('profile/', include('apps.profile.urls', namespace='profile')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
