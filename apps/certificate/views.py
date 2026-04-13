from django.views.generic import TemplateView


class IndexView(TemplateView):
    """证明开具首页"""
    template_name = 'certificate/index.html'
