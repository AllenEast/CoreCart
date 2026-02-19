# orders/services/checkout_service.py
from decimal import Decimal
from django.db import transaction

from cart.services.cart_service import CartService
from cart.models import CartItem
from catalog.models import ProductVariant
from orders.models import Order, OrderItem

from payments.services.payment_service import PaymentService  # ✅ qo‘sh


class CheckoutService:
    @staticmethod
    @transaction.atomic
    def checkout(user, phone: str, address: str, comment: str = "") -> Order:
        cart = CartService.get_or_create_cart(user)

        # CartItemlarni lock
        items = (
            CartItem.objects
            .select_for_update()
            # variant.discount OneToOne bo'lgani uchun select_related bilan N+1 ni yo'q qilamiz
            .select_related("variant", "variant__product", "variant__discount")
            .filter(cart=cart)
        )

        if not items.exists():
            raise ValueError("Cart is empty")

        # Order yaratamiz
        order = Order.objects.create(
            user=user,
            total_price=Decimal("0.00"),
            phone=phone,
            address=address,
            comment=comment,
        )

        total_price = Decimal("0.00")
        order_items = []

        # Variantlarni ham lock qilish uchun list
        variant_ids = [i.variant_id for i in items]
        variants = (
            ProductVariant.objects
            .select_for_update()
            .select_related("product")
            .filter(id__in=variant_ids, is_active=True)
        )
        vmap = {v.id: v for v in variants}

        for item in items:
            variant = vmap.get(item.variant_id)
            if not variant:
                raise ValueError("Variant not found or inactive.")

            if variant.stock_quantity < item.quantity:
                raise ValueError(f"{variant.product.name} uchun yetarli stock yo‘q")

            unit_price = item.get_unit_price()
            total_price += unit_price * item.quantity

            order_items.append(
                OrderItem(
                    order=order,
                    variant=variant,
                    sku=variant.sku,
                    product_name=variant.product.name,
                    variant_name=variant.name,
                    unit_price=unit_price,
                    quantity=item.quantity,
                )
            )

            # stock kamaytirish (DBga keyin bulk_update)
            variant.stock_quantity -= item.quantity

        # DBga yozish
        OrderItem.objects.bulk_create(order_items)
        ProductVariant.objects.bulk_update(list(vmap.values()), ["stock_quantity"])

        order.total_price = total_price
        order.save(update_fields=["total_price", "updated_at"])

        # cart tozalash
        cart.items.all().delete()

        # ✅ COD payment record avtomatik yaratiladi (xohlasang olib tashlaysan)
        PaymentService.get_or_create_cod_payment(order=order)

        return order
