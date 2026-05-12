from django.views.generic import TemplateView


class IndexView(TemplateView):
    """智能问答首页"""
    template_name = 'qa/index.html'
