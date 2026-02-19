from decimal import Decimal
from django.db import models
from django.utils import timezone

from orders.models import Order


class Payment(models.Model):
    # =======================
    # METHODS
    # =======================
    METHOD_COD = "cod"
    METHOD_MOCK = "mock"
    METHOD_STRIPE = "stripe"
    METHOD_PAYME = "payme"
    METHOD_CLICK = "click"

    METHOD_CHOICES = [
        (METHOD_COD, "Cash on delivery"),
        (METHOD_MOCK, "Mock (dev/test)"),
        (METHOD_STRIPE, "Stripe"),
        (METHOD_PAYME, "Payme (Paycom)"),
        (METHOD_CLICK, "Click"),
    ]

    # =======================
    # STATUSES
    # =======================
    STATUS_CREATED = "created"
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Created"),
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    # =======================
    # FIELDS
    # =======================
    # COD’da odatda 1 ta payment yetadi → OneToOne
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")

    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_COD)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CREATED)
    paid_at = models.DateTimeField(blank=True, null=True)

    # online providerlar uchun keyin kerak bo‘ladi:
    provider_ref = models.CharField(max_length=128, blank=True, default="", db_index=True)

    # debug/audit (ixtiyoriy)
    raw_request = models.JSONField(blank=True, null=True)
    raw_response = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_paid(self):
        if self.status == self.STATUS_PAID:
            return
        self.status = self.STATUS_PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at", "updated_at"])

    def mark_failed(self):
        if self.status == self.STATUS_FAILED:
            return
        self.status = self.STATUS_FAILED
        self.save(update_fields=["status", "updated_at"])

    def mark_cancelled(self):
        if self.status == self.STATUS_CANCELLED:
            return
        self.status = self.STATUS_CANCELLED
        self.save(update_fields=["status", "updated_at"])
