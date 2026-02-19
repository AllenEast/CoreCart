# cart/api/urls.py
from django.urls import path
from cart.api import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_detail, name="detail"),               # GET
    path("add/", views.cart_add, name="add"),                 # POST
    path("quantity/", views.cart_change_quantity, name="qty"),# PATCH
    path("remove/", views.cart_remove, name="remove"),        # DELETE
    path("clear/", views.cart_clear, name="clear"),           # POST
]
