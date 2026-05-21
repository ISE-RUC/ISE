from django.contrib import admin

from apps.certificate.models import CertificateRequest


@admin.register(CertificateRequest)
class CertificateRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'cert_type', 'applicant', 'status', 'first_reviewer', 'final_reviewer', 'created_at')
    list_filter = ('status', 'cert_type', 'created_at')
    search_fields = ('applicant__username', 'applicant__real_name', 'cert_type', 'purpose')
