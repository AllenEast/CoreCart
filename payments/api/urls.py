# payments/api/urls.py
from django.urls import path
from payments.api import views

urlpatterns = [
    path("cod/<int:order_id>/create/", views.cod_create, name="cod-create"),
    path("cod/<int:order_id>/mark_paid/", views.cod_mark_paid, name="cod-mark-paid"),

    # DEV/TEST ONLY (DEBUG=True)
    path("mock/<int:order_id>/pay/", views.mock_pay, name="mock-pay"),
    path("mock/<int:order_id>/fail/", views.mock_fail, name="mock-fail"),

    # CLICK (SHOP API) callbacks
    path("click/prepare/", views.click_prepare, name="click-prepare"),
    path("click/complete/", views.click_complete, name="click-complete"),
]
