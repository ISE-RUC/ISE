from django.contrib import admin

from apps.certificate.models import CertificateLog, CertificateMaterial, CertificateRequest


@admin.register(CertificateRequest)
class CertificateRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "reference_no", "cert_type", "applicant", "status", "created_at", "updated_at")
    list_filter = ("status", "cert_type", "created_at")
    search_fields = ("reference_no", "applicant__username", "applicant__real_name", "cert_type", "purpose")


@admin.register(CertificateMaterial)
class CertificateMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "request", "name", "is_required", "is_valid")
    list_filter = ("is_required", "is_valid")
    search_fields = ("request__reference_no", "name", "detail")


@admin.register(CertificateLog)
class CertificateLogAdmin(admin.ModelAdmin):
    list_display = ("id", "request", "action", "operator", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("request__reference_no", "action", "detail", "operator")
