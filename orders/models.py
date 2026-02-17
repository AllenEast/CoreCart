from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_paid(self):
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
        on_delete=models.PROTECT,  # ✅ order tarixini saqlash uchun CASCADE emas
        related_name="order_items",
    )

    # ✅ Snapshot fields (variant/product o‘zgarsa ham order saqlanadi)
    sku = models.CharField(max_length=50, null=True, blank=True)
    product_name = models.CharField(max_length=255, null=True, blank=True)
    variant_name = models.CharField(max_length=100, null=True, blank=True)

    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "variant"], name="unique_order_variant")
        ]

    def __str__(self):
        return f"{self.product_name} - {self.variant_name} x {self.quantity}"

    @property
    def total_price(self):
        return self.unit_price * self.quantity
