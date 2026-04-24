from django.shortcuts import render

from service_commercial.client_analytics.models import Dataset
from service_commercial.fiches_techniques.pages.models import Recipe


def home(request):
    latest_dataset = Dataset.objects.order_by("-updated_at").first()

    context = {
        "datasets_count": Dataset.objects.count(),
        "recipes_count": Recipe.objects.count(),
        "latest_dataset": latest_dataset,
    }
    return render(request, "main_page/home.html", context)
