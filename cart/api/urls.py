from django.urls import path
from .views import (
    cart_detail,
    cart_add,
    cart_change_quantity,
    cart_remove,
    cart_clear,
)

urlpatterns = [
    path("", cart_detail, name="cart-detail"),
    path("add/", cart_add, name="cart-add"),
    path("quantity/", cart_change_quantity, name="cart-change-quantity"),
    path("remove/", cart_remove, name="cart-remove"),
    path("clear/", cart_clear, name="cart-clear"),
]
