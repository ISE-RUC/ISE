from django.views.generic import TemplateView


class HomeView(TemplateView):
    """主页 - 前端展示用，暂不需要登录"""
    template_name = 'home.html'
