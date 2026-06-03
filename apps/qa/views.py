from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.views.generic import TemplateView

from .models import FAQEntry, FormTemplate, PolicyDocument


class IndexView(LoginRequiredMixin, TemplateView):
    """智能问答首页。"""

    template_name = "qa/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        faq_results = FAQEntry.objects.none()
        policy_results = PolicyDocument.objects.none()
        template_results = FormTemplate.objects.none()
        if query:
            faq_results = FAQEntry.objects.filter(
                Q(question__icontains=query) | Q(answer__icontains=query)
            )[:8]
            policy_results = PolicyDocument.objects.filter(title__icontains=query)[:8]
            template_results = FormTemplate.objects.filter(name__icontains=query)[:8]
        context.update(
            {
                "query": query,
                "faq_results": faq_results,
                "policy_results": policy_results,
                "template_results": template_results,
                "has_searched": bool(query),
            }
        )
        return context
