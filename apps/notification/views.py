from django.views.generic import TemplateView


class IndexView(TemplateView):
    """通知公告首页"""
    template_name = 'notification/index.html'
