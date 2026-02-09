from decimal import Decimal

from django.conf import settings
from django.db import models
from catalog.models import ProductVariant



class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart of {self.user}"

    @property
    def total_price(self) -> Decimal:
        """
        Cart ichidagi barcha item'lar summasi
        (discount bilan birga)
        """
        return sum(
            (item.total_price for item in self.items.all()),
            Decimal('0.00')
        )



class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['cart', 'variant'],
                name='unique_cart_variant'
            )
        ]

    def __str__(self):
        return f"{self.variant} x {self.quantity}"



    def get_unit_price(self) -> Decimal:
        """
        Bitta mahsulot narxi (discount bo‘lsa — hisoblab)
        """
        discount = getattr(self.variant, 'discount', None)

        if discount and discount.is_valid:
            return (
                self.variant.price
                * (Decimal('100') - discount.percent)
                / Decimal('100')
            )

        return self.variant.price

    @property
    def total_price(self) -> Decimal:
        """
        Item umumiy narxi (unit_price * quantity)
        """
        return self.get_unit_price() * self.quantity
