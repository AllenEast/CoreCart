from django.urls import path
from django.http import JsonResponse

def catalog_health(request):
    return JsonResponse({"status": "ok", "service": "catalog"})

urlpatterns = [
    path("health/", catalog_health, name="catalog-health"),
]
