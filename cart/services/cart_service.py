from django.db import transaction
from django.shortcuts import get_object_or_404
from cart.models import Cart, CartItem
from catalog.models import ProductVariant


class CartService:
    """
    Cart bilan bog‘liq barcha biznes-logika shu servisda.
    View faqat chaqiradi, DB logika bu yerda bo‘ladi.
    """

    @staticmethod
    def get_or_create_cart(user):
        """
        User uchun cart bor bo‘lsa oladi,
        bo‘lmasa yangi cart yaratadi.
        """
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart

    @staticmethod
    @transaction.atomic  # ❗ add_to_cart to‘liq bitta transaction
    def add_to_cart(user, variant_id: int, quantity: int = 1):

        # ❌ Noto‘g‘ri quantity bo‘lsa darrov to‘xtaydi
        if quantity < 1:
            raise ValueError('quantity must be greater than 0')

        # 🛒 User cartini olish (yoki yaratish)
        cart = CartService.get_or_create_cart(user)

        # 📦 Aktiv variantni olish
        variant = get_object_or_404(
            ProductVariant,
            id=variant_id,
            is_active=True
        )

        # 🔒 CartItem ni lock bilan olish
        # (bir vaqtning o‘zida 2 marta qo‘shilishining oldini oladi)
        item = (
            CartItem.objects
            .select_for_update()
            .filter(cart=cart, variant=variant)
            .first()
        )

        if item:
            # ➕ Agar oldin bor bo‘lsa quantity oshiramiz
            item.quantity += quantity
            item.save(update_fields=['quantity'])
        else:
            # ➕ Agar yo‘q bo‘lsa yangi CartItem yaratamiz
            item = CartItem.objects.create(
                cart=cart,
                variant=variant,
                quantity=quantity
            )

        return item

    @staticmethod
    @transaction.atomic
    def remove_from_cart(user, variant_id: int):
        """
        Cartdan bitta variantni butunlay o‘chiradi
        """
        cart = CartService.get_or_create_cart(user)

        CartItem.objects.filter(
            cart=cart,
            variant_id=variant_id
        ).delete()

    @staticmethod
    @transaction.atomic
    def change_quantity(user, variant_id: int, quantity: int):
        """
        Cart ichidagi item quantity sini o‘zgartiradi
        """

        cart = CartService.get_or_create_cart(user)

        # ❌ Agar quantity 0 yoki manfiy bo‘lsa — item o‘chadi
        if quantity < 1:
            CartItem.objects.filter(
                cart=cart,
                variant_id=variant_id
            ).delete()
            return

        # 🔒 CartItem ni lock bilan olish
        item = CartItem.objects.select_for_update().get(
            cart=cart,
            variant_id=variant_id
        )

        # ✏️ Quantity yangilash
        item.quantity = quantity
        item.save(update_fields=['quantity'])

        return item

    @staticmethod
    @transaction.atomic
    def clear_cart(user):
        """
        Cart ichidagi barcha itemlarni o‘chiradi
        (cartning o‘zi qoladi)
        """
        cart = CartService.get_or_create_cart(user)

        # ❗ cart.objects YO‘Q
        # cart — instance
        # items — related_name orqali kelgan manager
        cart.items.all().delete()
