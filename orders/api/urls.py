from django.urls import path, include
from rest_framework.routers import DefaultRouter
from orders.api.views import checkout, OrderViewSet

router = DefaultRouter()
router.register("", OrderViewSet, basename="orders")

urlpatterns = [
    path("checkout/", checkout, name="orders-checkout"),
    path("", include(router.urls)),
]
