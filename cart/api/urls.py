from django.urls import path
from django.http import JsonResponse

def cart_health(request):
    return JsonResponse({"status": "ok", "service": "cart"})

urlpatterns = [
    path("health/", cart_health, name="cart-health"),
]
