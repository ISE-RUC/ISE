from django.views.generic import TemplateView


class IndexView(TemplateView):
    """个人画像首页"""
    template_name = 'profile/index.html'
