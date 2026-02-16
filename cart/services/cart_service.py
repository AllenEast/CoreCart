from django.db import transaction
from django.shortcuts import get_object_or_404
from cart.models import Cart, CartItem
from catalog.models import ProductVariant


class CartService:
    @staticmethod
    def get_or_create_cart(user):
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart

    @staticmethod
    @transaction.atomic
    def add_to_cart(user, variant_id: int, quantity: int = 1):
        if quantity < 1:
            raise ValueError("quantity must be greater than 0")

        cart = CartService.get_or_create_cart(user)

        # ✅ Aktiv variantni olamiz
        variant = get_object_or_404(ProductVariant, id=variant_id, is_active=True)

        # ✅ Agar birinchi marta qo‘shilayotgan bo‘lsa ham stock yetarlimi?
        if variant.stock_quantity < quantity:
            raise ValueError("Not enough stock.")

        # ✅ Lock bilan item olish
        item = (
            CartItem.objects
            .select_for_update()
            .filter(cart=cart, variant=variant)
            .first()
        )

        if item:
            new_qty = item.quantity + quantity

            # ✅ Stockdan oshmasin
            if variant.stock_quantity < new_qty:
                raise ValueError("Not enough stock.")

            item.quantity = new_qty
            item.save(update_fields=["quantity"])
        else:
            item = CartItem.objects.create(
                cart=cart,
                variant=variant,
                quantity=quantity
            )

        return item

    @staticmethod
    @transaction.atomic
    def remove_from_cart(user, variant_id: int):
        cart = CartService.get_or_create_cart(user)

        CartItem.objects.filter(
            cart=cart,
            variant_id=variant_id
        ).delete()

    @staticmethod
    @transaction.atomic
    def change_quantity(user, variant_id: int, quantity: int):
        cart = CartService.get_or_create_cart(user)

        # 0 bo'lsa o‘chirish
        if quantity < 1:
            CartItem.objects.filter(cart=cart, variant_id=variant_id).delete()
            return None

        # ✅ Variantni tekshirish (active + mavjud)
        variant = get_object_or_404(ProductVariant, id=variant_id, is_active=True)

        # ✅ Stockdan oshmasin
        if variant.stock_quantity < quantity:
            raise ValueError("Not enough stock.")

        # ✅ Itemni lock bilan olish
        item = CartItem.objects.select_for_update().get(
            cart=cart,
            variant_id=variant_id
        )

        item.quantity = quantity
        item.save(update_fields=["quantity"])
        return item

    @staticmethod
    @transaction.atomic
    def clear_cart(user):
        cart = CartService.get_or_create_cart(user)
        cart.items.all().delete()
