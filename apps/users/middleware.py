from apps.users.models import AuditLog


class AuditLogMiddleware:
    """自动记录所有写操作（POST/PUT/DELETE/PATCH）的审计日志。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH') and request.user.is_authenticated:
            AuditLog.objects.create(
                user=request.user,
                action=f'{request.method} {request.path}',
                ip_address=self._get_ip(request),
            )
        return response

    def _get_ip(self, request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
