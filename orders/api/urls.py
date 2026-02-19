# orders/api/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from orders.api.views import OrderViewSet, checkout

router = DefaultRouter()
router.register("", OrderViewSet, basename="orders")

urlpatterns = [
    path("checkout/", checkout, name="orders-checkout"),
    path("", include(router.urls)),
]
