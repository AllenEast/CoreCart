from decimal import Decimal
from django.db import transaction

from cart.services.cart_service import CartService
from cart.models import CartItem
from catalog.models import ProductVariant
from orders.models import Order, OrderItem


class CheckoutService:
    @staticmethod
    @transaction.atomic
    def checkout(user, phone: str, address: str, comment: str = ""):
        # ✅ Cart bor bo‘lmasa yaratadi
        cart = CartService.get_or_create_cart(user)

        # 🔒 CartItem + Variantlarni lock qilib olamiz (bitta joyda)
        items = (
            CartItem.objects
            .select_for_update()
            .select_related("variant", "variant__product")
            .filter(cart=cart)
        )

        if not items.exists():
            raise ValueError("Cart is empty")

        total_price = Decimal("0.00")
        order_items = []

        # 📦 Order yaratamiz (total keyin ham set qilsa bo‘ladi)
        order = Order.objects.create(
            user=user,
            total_price=Decimal("0.00"),
            phone=phone,
            address=address,
            comment=comment,
        )

        for item in items:
            variant = item.variant  # items.select_related tufayli DBga qayta bormaydi

            if not variant.is_active:
                raise ValueError("Variant not found or inactive.")

            if variant.stock_quantity < item.quantity:
                raise ValueError(f"{variant.product.name} uchun yetarli stock yo‘q")

            unit_price = item.get_unit_price()  # ✅ sizda allaqachon discount hisoblaydi

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

            # 📉 stock kamaytirish
            variant.stock_quantity -= item.quantity
            variant.save(update_fields=["stock_quantity"])

        OrderItem.objects.bulk_create(order_items)

        order.total_price = total_price
        order.save(update_fields=["total_price", "updated_at"])

        cart.items.all().delete()
        return order
