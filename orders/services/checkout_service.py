from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404

from cart.models import Cart
from catalog.models import ProductVariant
from orders.models import Order, OrderItem


class CheckoutService:
    """
    Cart → Order o‘tkazish uchun servis.
    Barcha checkout logikasi bitta joyda.
    """

    @staticmethod
    @transaction.atomic  # ❗ Hammasi bitta DB transaction ichida ishlaydi
    def checkout(user, phone: str, address: str, comment: str = ""):

        # 🔒 Cartni lock bilan olish
        # Bir vaqtning o‘zida 2 ta checkout bo‘lib ketmasligi uchun
        cart = Cart.objects.select_for_update().get(user=user)

        # 🛒 Cart ichidagi barcha itemlarni olish
        # select_related → JOIN qiladi:
        # CartItem → ProductVariant → Product
        # Natijada N+1 query bo‘lmaydi
        items = cart.items.select_related(
            "variant",
            "variant__product"
        )

        # 🚫 Agar cart bo‘sh bo‘lsa — checkout yo‘q
        if not items.exists():
            raise ValueError("Cart is empty")

        total_price = Decimal("0.00")  # Order umumiy summasi
        order_items = []               # Keyin bulk_create qilish uchun

        # 🔁 Har bir cart item bo‘yicha yuramiz
        for item in items:

            # 🔒 Variantni alohida lock bilan olish
            # Chunki stock_quantity ni o‘zgartiramiz
            variant = (
                ProductVariant.objects
                .select_for_update()
                .get(id=item.variant_id)
            )

            # ❌ Agar stock yetarli bo‘lmasa — checkout to‘xtaydi
            if variant.stock_quantity < item.quantity:
                raise ValueError(
                    f"{variant.product.name} uchun yetarli stock yo‘q"
                )

            # 🎯 Variantda discount bormi yo‘qmi tekshiramiz
            # getattr → agar discount bo‘lmasa error chiqarmaydi
            discount = getattr(variant, "discount", None)

            # 💸 Agar discount mavjud va aktiv bo‘lsa — chegirmali narx
            if discount and discount.is_valid:
                unit_price = (
                    variant.price
                    * (Decimal("100") - discount.percent)
                    / Decimal("100")
                )
            else:
                # ❌ Discount yo‘q bo‘lsa — oddiy narx
                unit_price = variant.price

            # 🧮 Order umumiy summasini hisoblash
            total_price += unit_price * item.quantity

            # 🧱 OrderItem obyektini hozir DB ga yozmaymiz
            # bulk_create uchun listga yig‘amiz
            order_items.append(
                OrderItem(
                    variant=variant,
                    price=unit_price,      # ❗ checkout paytidagi narx FIX
                    quantity=item.quantity,
                )
            )

        # 📦 Order yaratish
        order = Order.objects.create(
            user=user,
            total_price=total_price,
            phone=phone,
            address=address,
            comment=comment,
        )

        # 🔗 Har bir OrderItem ni shu orderga bog‘laymiz
        for oi in order_items:
            oi.order = order

        # 🚀 OrderItem larni bitta query bilan DB ga yozish
        OrderItem.objects.bulk_create(order_items)

        # 📉 Stockni kamaytirish
        # Bu joyda variantlar oldindan lock qilingan
        for oi in order_items:
            oi.variant.stock_quantity -= oi.quantity
            oi.variant.save(update_fields=["stock_quantity"])

        # 🧹 Checkout tugagach cartni tozalash
        cart.items.all().delete()

        # ✅ Tayyor orderni qaytaramiz
        return order
