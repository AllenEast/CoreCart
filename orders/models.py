# orders/models.py
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

from catalog.models import ProductVariant


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_SHIPPED = "shipped"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    phone = models.CharField(max_length=20)
    address = models.TextField()
    comment = models.TextField(blank=True)

    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Bitta joyda qoidani saqlaymiz (service emas, model)
    STATUS_TRANSITIONS = {
        STATUS_PENDING: {STATUS_CONFIRMED, STATUS_CANCELLED},
        STATUS_CONFIRMED: {STATUS_SHIPPED, STATUS_CANCELLED},
        STATUS_SHIPPED: {STATUS_DELIVERED},
        STATUS_DELIVERED: set(),
        STATUS_CANCELLED: set(),
    }

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.STATUS_TRANSITIONS.get(self.status, set())

    def set_status(self, new_status: str, *, save: bool = True):
        if new_status == self.status:
            return  # idempotent

        valid_statuses = {c[0] for c in self.STATUS_CHOICES}
        if new_status not in valid_statuses:
            raise ValidationError("Invalid status")

        if not self.can_transition_to(new_status):
            raise ValidationError(f"Cannot change status {self.status} → {new_status}")

        self.status = new_status

        update_fields = ["status", "updated_at"]

        if new_status == self.STATUS_CANCELLED and self.cancelled_at is None:
            self.cancelled_at = timezone.now()
            update_fields.append("cancelled_at")

        if save:
            self.save(update_fields=update_fields)

    def mark_paid(self):
        if self.paid:
            return
        self.paid = True
        self.paid_at = timezone.now()
        self.save(update_fields=["paid", "paid_at", "updated_at"])

    def recalc_total(self, save: bool = True) -> Decimal:
        total = sum((i.total_price for i in self.items.all()), Decimal("0.00"))
        self.total_price = total
        if save:
            self.save(update_fields=["total_price", "updated_at"])
        return total

    def __str__(self):
        return f"Order #{self.id} - {self.user}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    sku = models.CharField(max_length=50, null=True, blank=True)
    product_name = models.CharField(max_length=255, null=True, blank=True)
    variant_name = models.CharField(max_length=100, null=True, blank=True)

    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "variant"], name="unique_order_variant")
        ]

    @property
    def total_price(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.product_name} - {self.variant_name} x {self.quantity}"
