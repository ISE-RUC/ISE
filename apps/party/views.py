from django.views.generic import TemplateView


class IndexView(TemplateView):
    """党团事务首页"""
    template_name = 'party/index.html'
