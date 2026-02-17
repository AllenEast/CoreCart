from django.urls import path
from orders.api.views import checkout

urlpatterns = [
    path("checkout/", checkout, name="orders-checkout"),
]
